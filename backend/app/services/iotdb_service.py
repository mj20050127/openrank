from iotdb.Session import Session
from datetime import datetime

def get_iotdb_data_for_dataease(repo_full_name: str):
    # 1. 路径转换逻辑，需与 health_pipeline.py 保持一致 [cite: 541-546]
    parts = repo_full_name.split("/")
    safe_parts = [p.replace("-", "_").replace(".", "_") for p in parts]
    device_id = f"root.openrank.github.{'.'.join(safe_parts)}"

    session = Session("127.0.0.1", "6667", "root", "root")
    try:
        session.open(False)
        # 执行查询，获取所有指标
        sql = f"SELECT * FROM {device_id} ORDER BY time ASC"
        dataset = session.execute_query_statement(sql)
        
        # 处理列名：将 root.openrank...metric_activity 简化为 metric_activity
        raw_columns = dataset.get_column_names()
        clean_headers = [col.split('.')[-1] if col != "Time" else "time" for col in raw_columns]
        
        result = []
        while dataset.has_next():
            row = dataset.next()
            fields = row.get_fields()
            # 组装为 DataEase 喜欢的扁平化字典
            row_dict = {"time": datetime.fromtimestamp(row.get_timestamp() / 1000).strftime("%Y-%m-%d")}
            for i, val in enumerate(fields):
                # row.get_fields() 不包含 Time，所以索引对齐 clean_headers[1:]
                row_dict[clean_headers[i+1]] = val
            result.append(row_dict)
        return result
    finally:
        session.close()