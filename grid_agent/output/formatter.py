"""
Output Formatter - 输出格式化
"""
from typing import Dict, Optional
import json


class OutputFormatter:
    """输出格式化器"""
    
    @staticmethod
    def to_json(data: Dict, pretty: bool = True) -> str:
        """转换为JSON字符串"""
        if pretty:
            return json.dumps(data, ensure_ascii=False, indent=2)
        return json.dumps(data, ensure_ascii=False)
    
    @staticmethod
    def format_result(result: Dict, output_key: Optional[str] = None) -> Dict:
        """
        格式化执行结果
        """
        if output_key:
            return {
                "status": "success",
                "data": result.get(output_key),
                "output_key": output_key
            }
        
        return {
            "status": "success",
            "data": result
        }