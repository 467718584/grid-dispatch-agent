"""
飞书流式输出格式化工具

被 api/server.py 和 api/dispatch_api.py 共用
"""

import json


class FeishuStreamOutput:
    """飞书流式输出格式化工具"""
    
    DEFAULT_ROLE = {
        "id": "grid-dispatch-agent",
        "name": "电网调度智能体",
        "avatar": "/assets/agent/grid-agent.png"
    }
    
    # 步骤中英文映射
    STEP_MAPPING = {
        "init": {"name": "初始化", "desc": "正在连接电网系统...", "component": "step-init"},
        "get_constraint": {"name": "读取约束", "desc": "正在读取发电调度约束数据...", "component": "step-constraint"},
        "calculate": {"name": "调度计算", "desc": "正在进行防洪调度优化计算...", "component": "step-calculate"},
        "model_list": {"name": "库区查询", "desc": "正在获取流域库区列表...", "component": "step-model-list"},
        "result_table": {"name": "结果读取", "desc": "正在读取计算结果数据...", "component": "step-result"},
        "save_scheme": {"name": "发布方案", "desc": "正在保存并发布调度方案...", "component": "step-save"},
        "get_plan": {"name": "计划读取", "desc": "正在读取电网下达计划...", "component": "step-plan"},
        "modify_constraint": {"name": "修改约束", "desc": "正在调整约束参数...", "component": "step-modify"},
    }
    
    @staticmethod
    def format_text(chat_id: int, conversation_id: str, message_id: str,
                   content: str, complete: bool = False, finish: bool = False,
                   component_name: str = None, step_name: str = None, step_desc: str = None) -> str:
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "text",
            "content": content,
            "complete": complete,
            "finish": finish,
            "status": 2 if (not complete and not finish) else 1,  # 2=加载中
            "role": FeishuStreamOutput.DEFAULT_ROLE
        }
        if component_name:
            data["componentName"] = component_name
        if step_name:
            data["stepName"] = step_name
        if step_desc:
            data["stepDesc"] = step_desc
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    
    @staticmethod
    def format_markdown(chat_id: int, conversation_id: str, message_id: str,
                       content: str, complete: bool = False, finish: bool = False,
                       component_name: str = None, step_name: str = None, step_desc: str = None) -> str:
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "markdown",
            "content": content,
            "complete": complete,
            "finish": finish,
            "status": 1,
            "role": FeishuStreamOutput.DEFAULT_ROLE
        }
        if component_name:
            data["componentName"] = component_name
        if step_name:
            data["stepName"] = step_name
        if step_desc:
            data["stepDesc"] = step_desc
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    
    @staticmethod
    def format_result(chat_id: int, conversation_id: str, message_id: str,
                     result_data: dict, complete: bool = True,
                     component_name: str = None, step_name: str = None, step_desc: str = None) -> str:
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "result",
            "content": result_data,
            "complete": complete,
            "finish": False,
            "status": 1,
            "role": FeishuStreamOutput.DEFAULT_ROLE
        }
        if component_name:
            data["componentName"] = component_name
        if step_name:
            data["stepName"] = step_name
        if step_desc:
            data["stepDesc"] = step_desc
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    
    @staticmethod
    def format_error(chat_id: int, conversation_id: str, message_id: str,
                    error_msg: str, component_name: str = None) -> str:
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "error",
            "content": error_msg,
            "complete": True,
            "finish": False,
            "status": 3,  # 3=错误
            "role": FeishuStreamOutput.DEFAULT_ROLE
        }
        if component_name:
            data["componentName"] = component_name
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    
    @staticmethod
    def format_finish(chat_id: int, conversation_id: str, message_id: str,
                    summary: str = None) -> str:
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "finish",
            "content": summary or "处理完成",
            "complete": True,
            "finish": True,
            "status": 1,
            "role": FeishuStreamOutput.DEFAULT_ROLE
        }
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"