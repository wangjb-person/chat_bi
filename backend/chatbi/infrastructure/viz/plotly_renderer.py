import pandas as pd

from chatbi.infrastructure.llm.client import LlmClient
from chatbi.infrastructure.llm.messages import system_message, user_message


class PlotlyRenderer:
    """基于 LLM 生成 Plotly 代码并渲染图表（演示版；生产应改为模板或 DSL）。"""

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    def generate_code(self, *, question: str, sql: str, df_metadata: str) -> str:
        messages = [
            system_message(
                "你是一个数据可视化专家。根据用户的问题、SQL查询和数据结构，"
                "生成完整的Python Plotly代码来创建图表。\n"
                "要求：\n"
                "1. 只返回Python代码，不要有任何解释\n"
                "2. 代码必须包含 plotly 库的导入\n"
                "3. 生成的 figure 对象必须赋值给 fig 变量\n"
                "4. 根据数据特征选择合适的图表类型\n"
                "5. 确保代码可以直接运行"
            ),
            user_message(
                f"问题: {question}\n"
                f"SQL: {sql}\n"
                f"数据结构:\n{df_metadata}\n\n"
                f"请生成 Python Plotly 代码来可视化这些数据。"
            ),
        ]
        return self._llm.complete(messages)

    def render_figure(self, plotly_code: str, df: pd.DataFrame, dark_mode: bool = False):
        import plotly.express as px
        import plotly.graph_objects as go

        local_vars = {"df": df, "px": px, "go": go, "pd": pd}
        try:
            exec(plotly_code, {}, local_vars)
            fig = local_vars.get("fig")
            if fig is None:
                raise ValueError("代码没有生成 fig 对象")
            return fig
        except Exception as e:
            raise Exception(f"执行图表代码失败: {str(e)}") from e
