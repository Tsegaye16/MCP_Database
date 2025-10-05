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


def build_query_agent(llm, list_tables_tool, get_schema_tool):
    return create_react_agent(
        llm,
        tools=[list_tables_tool, get_schema_tool],
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


def build_exec_agent(llm):
    return create_react_agent(
        llm,
        tools=[db_exec_tool],
    )


def normalize_result_to_df(result):
    if isinstance(result, list):
        if len(result) == 0:
            return pd.DataFrame()
        if isinstance(result[0], dict):
            return pd.DataFrame(result)
        return pd.DataFrame(result)
    if isinstance(result, dict):
        return pd.DataFrame([result])
    try:
        return pd.read_json(result)
    except Exception:
        return pd.DataFrame({"result": [result]})


def main():
    st.set_page_config(page_title="DB Chatbot", page_icon="💬", layout="centered")
    st.title("💬 Database Chatbot")
    st.caption("Ask questions in natural language. The bot will query your database.")

    with st.sidebar:
        
        st.subheader("How to test this bot")
        st.markdown(
            """
            **What this bot does**

            - Understands plain-English questions about your database
            - Generates a SQL query internally and returns answers in natural language

            **Tables available**

            - **users**: `user_id`, `name`, `email`, `hobby`, `job`, `age`
            - **products**: `product_id`, `name`, `category`, `price`, `stock`
            - **orders**: `order_id`, `user_id`, `order_date`, `status`, `total_amount`
            - **order_items**: `order_item_id`, `order_id`, `product_id`, `quantity`, `unit_price`

            **Key relationships**

            - A **user** has many **orders** (`orders.user_id -> users.user_id`)
            - An **order** has many **order_items** (`order_items.order_id -> orders.order_id`)
            - A **product** appears in many **order_items** (`order_items.product_id -> products.product_id`)

            **Good questions to try**

            - "How many users are in the system?"
            - "List users and their ages."
            - "What are the top 3 most expensive products?"
            - "Show total sales amount by user."
            - "Which products are out of stock or low on stock?"
            - "How many orders did Jane Smith place, and what's the total spent?"
            - "List orders with their items and totals for John Doe."

            **Tips for better results**

            - Be specific (e.g., name the user or product category)
            - Include filters (date ranges, statuses like `completed`, `shipped`)
            - Ask for aggregations (sum, average, count, top N)
            - You can reference columns listed above; the bot handles the joins
            """
        )

    db, llm, list_tables_tool, get_schema_tool, query_tool = get_db_and_tools()

    if not (list_tables_tool and get_schema_tool):
        st.error("Database tools are not available. Check DATABASE_URL and packages.")
        return

    if "history" not in st.session_state:
        st.session_state.history = []

    user_input = st.chat_input("Ask about users, products, orders…")

    for role, msg in st.session_state.history:
        with st.chat_message(role):
            st.write(msg)

    if user_input:
        st.session_state.history.append(("user", user_input))
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                query_agent = build_query_agent(llm, list_tables_tool, get_schema_tool)

                greeting_terms = {"hi", "hello", "hey", "yo", "good morning", "good afternoon", "good evening"}
                if user_input.strip().lower() in greeting_terms:
                    final_text = "Hello! Ask me about your users, products, or orders — for example: 'Show total sales amount by user.'"
                else:
                    system_instructions_q = (
                        "You write SQL for Postgres to answer the user's question. "
                        "First list available tables, then inspect relevant schemas. "
                        "Return ONLY a valid SQL query with no commentary. Do NOT mention tools or SQL to the user."
                    )
                    plan = query_agent.invoke({
                        "messages": [("system", system_instructions_q), ("user", user_input)]
                    })
                    sql_query = plan["messages"][-1].content

                    exec_agent = build_exec_agent(llm)
                    system_instructions_e = (
                        "Execute the SQL internally and respond with a short, friendly, non-technical answer. "
                        "Do not mention SQL, table names, schemas, or any internal tools."
                    )
                    result = exec_agent.invoke({
                        "messages": [("system", system_instructions_e), ("user", sql_query)]
                    })
                    final_text = result["messages"][-1].content

                final_text = re.sub(r"```[\s\S]*?```", "", final_text).strip()
                final_text = re.sub(r"db_exec_tool", "the database", final_text, flags=re.IGNORECASE)
                final_text = re.sub(r"\bSQL\b", "the database", final_text, flags=re.IGNORECASE)

                st.write(final_text)

                st.session_state.history.append(("assistant", final_text))


if __name__ == "__main__":
    main()


