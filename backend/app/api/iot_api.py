from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict, Any
from iotdb.Session import Session
from iotdb.utils.IoTDBConstants import TSDataType
from datetime import datetime
import logging
import math

# 初始化路由
router = APIRouter()
logger = logging.getLogger(__name__)

# IoTDB 配置 (请根据实际情况修改)
IOTDB_HOST = "127.0.0.1"
IOTDB_PORT = "6667"
IOTDB_USER = "root"
IOTDB_PW = "root"

def get_iotdb_session():
    """建立并返回 IoTDB 会话"""
    session = Session(IOTDB_HOST, IOTDB_PORT, IOTDB_USER, IOTDB_PW)
    session.open(False)
    return session

def sanitize_value(val: Any) -> Any:
    """
    清洗数据：
    1. 将 numpy 类型转换为原生 Python 类型
    2. 将 NaN/Inf 转换为 None (JSON 不支持 NaN)
    """
    # 处理 numpy 类型 (通过 .item() 转换为原生类型)
    if hasattr(val, "item"):
        val = val.item()
    
    # 处理浮点数中的特殊值 NaN / Inf
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
            
    return val

def extract_field_value(field: Any) -> Any:
    """
    安全地从 IoTDB Field 对象中提取值，并进行类型清洗。
    """
    raw_val = None

    # 1. 基础情况：如果是 None 或 IoTDB 的 Null
    if field is None:
        return None
    if hasattr(field, 'is_null') and field.is_null():
        return None

    # 2. 如果不是 Field 对象，而是直接的值
    if not hasattr(field, 'get_data_type'):
        raw_val = field
    else:
        # 3. 根据 DataType 提取值
        try:
            dt = field.get_data_type()
            if dt == TSDataType.BOOLEAN:
                raw_val = field.get_bool_value()
            elif dt == TSDataType.INT32:
                raw_val = field.get_int_value()
            elif dt == TSDataType.INT64:
                raw_val = field.get_long_value()
            elif dt == TSDataType.FLOAT:
                raw_val = field.get_float_value()
            elif dt == TSDataType.DOUBLE:
                raw_val = field.get_double_value()
            elif dt == TSDataType.TEXT:
                # 某些版本返回 bytes，需要 decode
                v = field.get_string_value()
                if isinstance(v, bytes):
                    raw_val = v.decode('utf-8')
                else:
                    raw_val = v
            else:
                # 尝试通用方法
                if hasattr(field, 'get_value'):
                    raw_val = field.get_value()
                else:
                    raw_val = str(field)
        except Exception:
            # 兜底：如果提取报错，强制转字符串
            raw_val = str(field)

    # 4. 最后一步：清洗值 (处理 numpy 和 NaN)
    return sanitize_value(raw_val)

@router.get("/export", response_model=List[Dict[str, Any]])
def export_iotdb_to_dataease(
    repo: str = Query(..., description="仓库全名，例如 X-lab2017/open-digger")
):
    """
    DataEase 专用 API：从 IoTDB 导出时序宽表数据
    """
    # 1. 路径转换
    try:
        parts = repo.split("/")
        if len(parts) != 2:
            raise ValueError("仓库格式必须为 owner/repo")
        
        safe_parts = [p.replace("-", "_").replace(".", "_") for p in parts]
        device_id = f"root.openrank.github.{'.'.join(safe_parts)}"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"仓库路径解析错误: {str(e)}")

    session = None
    try:
        session = get_iotdb_session()
        
        # 2. 路径探测
        check_sql = f"SHOW DEVICES {device_id}"
        check_result = session.execute_query_statement(check_sql)
        if not check_result.has_next():
            logger.warning(f"IoTDB 中未找到设备路径: {device_id}")
            return [] 

        # 3. 执行 SQL 查询
        sql = f"SELECT * FROM {device_id} ORDER BY time ASC"
        dataset = session.execute_query_statement(sql)
        
        # 4. 解析列名
        raw_columns = dataset.get_column_names()
        clean_headers = []
        for col in raw_columns:
            if col == "Time":
                clean_headers.append("time")
            else:
                clean_headers.append(col.split('.')[-1])

        result = []
        while dataset.has_next():
            row = dataset.next()
            fields = row.get_fields()
            
            # 时间戳转换
            ts = row.get_timestamp()
            row_dict = {
                "time": datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
            }
            
            # 5. 提取并映射数值
            # 注意：fields 索引从 0 开始，对应 clean_headers[1:] (跳过 time)
            for i, field_obj in enumerate(fields):
                # 防止列数对不上导致越界
                if i + 1 < len(clean_headers):
                    col_name = clean_headers[i + 1]
                    # 使用新的提取函数
                    row_dict[col_name] = extract_field_value(field_obj)
                
            result.append(row_dict)

        return result

    except Exception as e:
        logger.error(f"查询 IoTDB 失败 ({repo}): {str(e)}")
        # 打印详细堆栈方便调试
        import traceback
        traceback.print_exc()
        return []
    finally:
        if session:
            session.close()