import os
import re
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain.tools import Tool
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from sqlalchemy import inspect


load_dotenv()


@st.cache_resource(show_spinner=False)
def get_llm():
    api_key = os.getenv("GOOGLE_API_KEY")
    os.environ["GOOGLE_API_KEY"] = api_key or ""
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash")


@st.cache_resource(show_spinner=False)
def get_db_and_tools():
    database_url = os.getenv("DATABASE_URL")
    db = SQLDatabase.from_uri(database_url)
    llm = get_llm()
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = toolkit.get_tools()
    list_tables_tool = next((t for t in tools if t.name == "sql_db_list_tables"), None)
    get_schema_tool = next((t for t in tools if t.name == "sql_db_schema"), None)
    query_tool = next((t for t in tools if t.name == "sql_db_query"), None)
    return db, llm, list_tables_tool, get_schema_tool, query_tool


def build_agent(llm, list_tables_tool, get_schema_tool):
    # One agent with all DB tools (LLM-driven)
    return create_react_agent(
        llm,
        tools=[list_tables_tool, get_schema_tool, db_exec_tool],
    )


@tool
def db_exec_tool(query: str) -> str:
    """Execute the provided SQL query against the configured database and return the raw result or an error string."""
    query = query.replace("```sql", "").replace("```", "").strip()
    db, *_rest = get_db_and_tools()
    try:
        result = db.run_no_throw(query)
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def get_db_metadata(sql_db: SQLDatabase):
    try:
        engine = sql_db._engine
        insp = inspect(engine)
        tables = sorted(list(sql_db.get_usable_table_names()))
        columns_by_table = {}
        relationships = []
        for t in tables:
            try:
                cols = insp.get_columns(t)
                columns_by_table[t] = [c.get("name") for c in cols]
            except Exception:
                columns_by_table[t] = []
            try:
                fks = insp.get_foreign_keys(t)
                for fk in fks:
                    referred_table = fk.get("referred_table")
                    constrained_cols = fk.get("constrained_columns") or []
                    referred_cols = fk.get("referred_columns") or []
                    relationships.append(
                        f"{t}({', '.join(constrained_cols)}) -> {referred_table}({', '.join(referred_cols)})"
                    )
            except Exception:
                pass
        return tables, columns_by_table, relationships
    except Exception:
        return [], {}, []


def suggest_questions(tables, columns_by_table):
    suggestions = []
    if tables:
        suggestions.append("List all tables")
    if any('route' in t.lower() for t in tables) and any('rate' in t.lower() or 'price' in t.lower() for t in tables):
        suggestions.append("Give me a route detail with the cheapest service rate")
    if not suggestions and tables:
        t0 = tables[0]
        suggestions.append(f"Show the first 5 rows from {t0}")
    return suggestions[:6]


def render_sidebar_dynamic(sql_db: SQLDatabase):
    st.subheader("Connection")
    st.markdown("Using configuration from your .env file.")

    st.subheader("Database overview")
    tables, columns_by_table, relationships = get_db_metadata(sql_db)

    if not tables:
        st.write("No tables detected or connection unavailable.")
        return

    st.markdown("**Tables available**")
    st.write(", ".join(tables))

    st.markdown("**Key relationships**")
    if relationships:
        for rel in relationships[:12]:
            st.write(f"- {rel}")
        if len(relationships) > 12:
            st.write(f"… and {len(relationships) - 12} more")
    else:
        st.write("No foreign-key relationships detected.")

    st.markdown("**Good questions to try**")
    for q in suggest_questions(tables, columns_by_table):
        st.write(f"- {q}")


# --- Visualization helpers ---

def wants_chart(user_text: str) -> str | None:
    t = user_text.lower()
    if "line" in t and ("chart" in t or "graph" in t or "plot" in t):
        return "line"
    if ("bar" in t or "column" in t) and ("chart" in t or "graph" in t or "plot" in t):
        return "bar"
    if "area" in t and ("chart" in t or "graph" in t or "plot" in t):
        return "area"
    if "scatter" in t and ("chart" in t or "graph" in t or "plot" in t):
        return "scatter"
    return None


def extract_markdown_table(text: str) -> tuple[str, pd.DataFrame | None]:
    # Split summary from the first markdown table block
    lines = text.splitlines()
    start, sep, end = -1, -1, -1
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "|" in line.strip():
            # header candidate found
            if i + 1 < len(lines) and re.match(r"^\s*\|\s*[-: ]+\|", lines[i + 1]):
                start = i
                sep = i + 1
                # find end of table (first non table-looking line after sep)
                j = sep + 1
                while j < len(lines) and lines[j].strip().startswith("|"):
                    j += 1
                end = j
                break
    if start == -1:
        return text, None

    summary = "\n".join(lines[:start]).strip()
    table_lines = lines[start:end]
    if len(table_lines) < 2:
        return text, None
    headers = [h.strip() for h in table_lines[0].strip().strip("|").split("|")]
    rows = []
    for r in table_lines[2:]:
        parts = [c.strip() for c in r.strip().strip("|").split("|")]
        if len(parts) == len(headers):
            rows.append(parts)
    if not rows:
        return text, None
    df = pd.DataFrame(rows, columns=headers)
    # Attempt to numeric-cast value columns
    for c in df.columns:
        try:
            df[c] = pd.to_numeric(df[c])
        except Exception:
            pass
    return summary, df


def render_chart(df: pd.DataFrame, chart_type: str):
    if df is None or df.empty:
        return False
    # Choose x as first column; y as numeric columns (excluding x)
    x_col = df.columns[0]
    numeric_cols = [c for c in df.columns if c != x_col and pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        return False
    chart_df = df[[x_col] + numeric_cols].set_index(x_col)
    if chart_type == "line":
        st.line_chart(chart_df)
        return True
    if chart_type == "bar":
        st.bar_chart(chart_df)
        return True
    if chart_type == "area":
        try:
            st.area_chart(chart_df)
            return True
        except Exception:
            st.line_chart(chart_df)
            return True
    if chart_type == "scatter":
        try:
            st.scatter_chart(chart_df)
            return True
        except Exception:
            st.line_chart(chart_df)
            return True
    st.line_chart(chart_df)
    return True


def main():
    st.set_page_config(page_title="DB Chatbot", page_icon="💬", layout="centered")
    st.title("💬 Database Chatbot")
    st.caption("Ask questions in natural language. The bot will query your database.")

    db, llm, list_tables_tool, get_schema_tool, query_tool = get_db_and_tools()

    with st.sidebar:
        render_sidebar_dynamic(db)

    if not (list_tables_tool and get_schema_tool):
        st.error("Database tools are not available. Check DATABASE_URL and packages.")
        return

    # Persist chat and rendered payloads
    if "history" not in st.session_state:
        st.session_state.history = []
    if "render_payloads" not in st.session_state:
        st.session_state.render_payloads = []  # aligned with history; each item is None or {summary, table_markdown, chart_type, df_records, df_columns}

    user_input = st.chat_input("Ask about tables, relationships, or data… (e.g., 'shipments by route as a line chart')")

    # Re-render all previous messages with their payloads so charts persist
    for idx, (role, msg) in enumerate(st.session_state.history):
        with st.chat_message(role):
            payload = st.session_state.render_payloads[idx] if idx < len(st.session_state.render_payloads) else None
            if role == "assistant" and isinstance(payload, dict):
                summary = payload.get("summary")
                chart_type = payload.get("chart_type")
                df_records = payload.get("df_records")
                df_columns = payload.get("df_columns")
                table_markdown = payload.get("table_markdown")

                if summary:
                    st.write(summary)
                df = None
                if df_records and df_columns:
                    try:
                        df = pd.DataFrame(df_records, columns=df_columns)
                    except Exception:
                        df = None
                if chart_type and df is not None:
                    if not render_chart(df, chart_type):
                        if table_markdown:
                            st.markdown(table_markdown)
                        else:
                            st.write(msg)
                    else:
                        with st.expander("Show data table"):
                            st.dataframe(df, use_container_width=True)
                else:
                    # no chart; prefer markdown table if present
                    if table_markdown and "|" in table_markdown and re.search(r"\n\|[-: ]+\|", table_markdown):
                        st.markdown(table_markdown)
                    else:
                        st.write(msg)
            else:
                st.write(msg)

    if user_input:
        st.session_state.history.append(("user", user_input))
        st.session_state.render_payloads.append(None)
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                greeting_terms = {"hi", "hello", "hey", "yo", "good morning", "good afternoon", "good evening"}
                lower_input = user_input.strip().lower()

                if lower_input in greeting_terms:
                    final_text = "Hello! Ask me about your tables, relationships, or data — for example: ‘Shipments by route as a line chart’."
                else:
                    agent = build_agent(llm, list_tables_tool, get_schema_tool)
                    system_msg = (
                        "You are a database analyst. Use the tools to list tables and fetch relevant schemas, then generate a correct Postgres query with quoted identifiers and execute it via db_exec_tool. "
                        "Prefer user-friendly details over raw IDs: where possible, join to include human-friendly names (e.g., branch names, service type names). "
                        "Choose exact table/column names from the tools—never invent names. If a tool call fails due to casing/missing relation, adjust quoting and retry once. "
                        "Respond for non-technical users: first provide a concise plain-English summary (one or two sentences). Then include a small Markdown table (max 10 rows) with clear column headers suitable for charting (e.g., ‘Route’, ‘Shipments’). Do NOT show SQL or mention tools."
                    )
                    result = agent.invoke({
                        "messages": [("system", system_msg), ("user", user_input)]
                    })
                    final_text = result["messages"][-1].content

                # Sanitize (keep whitespace for Markdown tables)
                final_text = re.sub(r"```[\s\S]*?```", "", final_text).strip()
                final_text = re.sub(r"db_exec_tool", "the database", final_text, flags=re.IGNORECASE)
                final_text = re.sub(r"\bSQL\b", "the database", final_text, flags=re.IGNORECASE)

                # If a chart is requested, try to parse a Markdown table and render chart + summary
                chart_type = wants_chart(user_input)
                summary, df = extract_markdown_table(final_text)

                render_payload = {"summary": summary or final_text}
                rendered = False

                if chart_type and df is not None:
                    # Render chart and persist payload
                    if summary:
                        st.write(summary)
                    if render_chart(df, chart_type):
                        with st.expander("Show data table"):
                            st.dataframe(df, use_container_width=True)
                        render_payload.update({
                            "chart_type": chart_type,
                            "df_records": df.to_dict(orient="records"),
                            "df_columns": list(df.columns),
                            "table_markdown": None,
                        })
                        rendered = True
                    else:
                        # fallback: show markdown
                        st.markdown(final_text)
                        render_payload.update({"table_markdown": final_text})
                        rendered = True
                else:
                    # Render default (table or text)
                    if "|" in final_text and re.search(r"\n\|[-: ]+\|", final_text):
                        st.markdown(final_text)
                        render_payload.update({"table_markdown": final_text})
                        rendered = True
                    else:
                        st.write(final_text)
                        rendered = True

                st.session_state.history.append(("assistant", final_text))
                st.session_state.render_payloads.append(render_payload)


if __name__ == "__main__":
    main()


