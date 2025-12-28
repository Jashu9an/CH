#!/usr/bin/env python3
"""
Упрощенное нагрузочное тестирование ClickHouse
"""

import clickhouse_connect
import time
import statistics
import concurrent.futures
import json
from datetime import datetime

def test_performance():
    client = clickhouse_connect.get_client(host='localhost', port=8123, user='default', password='')
    
    print("🚀 Нагрузочное тестирование ClickHouse e-commerce")
    print("=" * 50)
    
    # Тестовые запросы
    queries = [
        {
            'name': 'COUNT всех товаров',
            'raw_query': "SELECT COUNT(*) FROM ecommerce.ecom_offers",
            'mv_query': None
        },
        {
            'name': 'COUNT по категориям (TOP 10)',
            'raw_query': "SELECT category_id, COUNT(*) as cnt FROM ecommerce.ecom_offers GROUP BY category_id ORDER BY cnt DESC LIMIT 10",
            'mv_query': "SELECT category_id, SUM(products_count) as cnt FROM ecommerce.catalog_by_category_mv GROUP BY category_id ORDER BY cnt DESC LIMIT 10"
        },
        {
            'name': 'Статистика по топ категории',
            'raw_query': "SELECT COUNT(*), AVG(price), MIN(price), MAX(price) FROM ecommerce.ecom_offers WHERE category_id = 7508",
            'mv_query': "SELECT SUM(total_price)/SUM(products_count) as avg_price, min_price, max_price FROM ecommerce.catalog_by_category_mv WHERE category_id = 7508"
        },
        {
            'name': 'Топ брендов по категории',
            'raw_query': "SELECT vendor, COUNT(*) FROM ecommerce.ecom_offers WHERE category_id = 7508 AND vendor != '' AND vendor != 'Unknown' GROUP BY vendor ORDER BY COUNT(*) DESC LIMIT 5",
            'mv_query': "SELECT vendor, SUM(products_count) FROM ecommerce.catalog_by_brand_mv WHERE category_id = 7508 GROUP BY vendor ORDER BY SUM(products_count) DESC LIMIT 5"
        }
    ]
    
    results = {}
    
    for test_query in queries:
        print(f"\n {test_query['name']}")
        print("-" * 40)
        
        # Тест сырых данных
        if test_query['raw_query']:
            raw_times = []
            for i in range(5):
                start = time.time()
                try:
                    rows = client.query(test_query['raw_query']).result_rows
                    execution_time = time.time() - start
                    raw_times.append(execution_time)
                except Exception as e:
                    print(f"Ошибка в сырых данных: {e}")
                    break
            
            if raw_times:
                avg_raw = statistics.mean(raw_times)
                min_raw = min(raw_times)
                max_raw = max(raw_times)
                print(f"Сырые:   {avg_raw:.4f}s (min: {min_raw:.4f}s, max: {max_raw:.4f}s)")
                results[f"{test_query['name']}_raw"] = {'avg': avg_raw, 'min': min_raw, 'max': max_raw}
        
        # Тест МВ
        if test_query['mv_query']:
            try:
                mv_times = []
                for i in range(5):
                    start = time.time()
                    rows = client.query(test_query['mv_query']).result_rows
                    execution_time = time.time() - start
                    mv_times.append(execution_time)
                
                avg_mv = statistics.mean(mv_times)
                min_mv = min(mv_times)
                max_mv = max(mv_times)
                print(f"МВ:      {avg_mv:.4f}s (min: {min_mv:.4f}s, max: {max_mv:.4f}s)")
                results[f"{test_query['name']}_mv"] = {'avg': avg_mv, 'min': min_mv, 'max': max_mv}
                
                # расчет ускорения
                if raw_times:
                    speedup = avg_raw / avg_mv
                    print(f"Ускорение: {speedup:.2f}x")
                    results[f"{test_query['name']}_speedup"] = speedup
                    
            except Exception as e:
                print(f"Ошибка в МВ: {e}")
    
    # Нагрузочное тестирование
    print(f"\n⚡ Нагрузочное тестирование...")
    concurrent_queries = [
        "SELECT COUNT(*) FROM ecommerce.ecom_offers",
        "SELECT category_id, COUNT(*) FROM ecommerce.ecom_offers GROUP BY category_id LIMIT 5",
        "SELECT vendor, COUNT(*) FROM ecommerce.ecom_offers WHERE vendor != '' GROUP BY vendor LIMIT 10"
    ]
    
    def run_query(query):
        start = time.time()
        try:
            client.query(query)
            return time.time() - start
        except:
            return 10.0  # ошибка/таймаут
    
    # Параллельное выполнение
    total_times = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_query, q) for q in concurrent_queries for _ in range(3)]
        
        for future in concurrent.futures.as_completed(futures):
            execution_time = future.result()
            total_times.append(execution_time)
    
    if total_times:
        avg_response = statistics.mean(total_times)
        max_response = max(total_times)
        total_queries = len(total_times)
        total_time = sum(total_times)
        qps = total_queries / total_time
        
        print(f"Среднее время ответа: {avg_response:.4f}s")
        print(f"Максимальное время: {max_response:.4f}s") 
        print(f"QPS: {qps:.2f}")
        
        results['load_test'] = {
            'avg_response': avg_response,
            'max_response': max_response,
            'total_queries': total_queries,
            'qps': qps
        }
    
    # Сохранение результатов
    results['timestamp'] = datetime.now().isoformat()
    results['dataset_size'] = '3.99M records'
    
    with open('C:/VSCode projects/Databases/CH/performance_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Генерация отчета
    print(f"\nИТОГИ НАГРУЗОЧНОГО ТЕСТИРОВАНИЯ")
    print("=" * 50)
    
    speedups = []
    for key, value in results.items():
        if key.endswith('_speedup'):
            speedups.append(value)
            query_name = key.replace('_speedup', '')
            print(f"{query_name}: {value:.2f}x ускорение")
    
    if speedups:
        avg_speedup = statistics.mean(speedups)
        print(f"\nСреднее ускорение: {avg_speedup:.2f}x")
        print(f"Максимальное ускорение: {max(speedups):.2f}x")
        print(f"Минимальное ускорение: {min(speedups):.2f}x")
    
    if 'load_test' in results:
        load = results['load_test']
        print(f"\n⚡ Нагрузочный тест: {load['total_queries']} запросов")
        print(f"QPS: {load['qps']:.2f} запросов/сек")
        print(f"Средний ответ: {load['avg_response']:.4f}s")
    
    return results

if __name__ == '__main__':
    try:
        test_performance()
        print(f"\n✅ Тестирование завершено успешно!")
        print(f"📄 Детальные результаты в performance_results.json")
    except Exception as e:
        print(f"Ошибка: {e}")
