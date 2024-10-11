from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq


def init_database(user, password, host, port, database):
    db_uri = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
    return SQLDatabase.from_uri(db_uri)

def get_sql_chain(db):
    template = """
    You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
    Based on the table schema below, write a SQL query that would answer the user's question. Take the conversation history into account.
    
    <SCHEMA>{schema}</SCHEMA>
    
    Conversation History: {chat_history}
    
    Write only the SQL query and nothing else. Do not wrap the SQL query in any other text, not even brackets.
    
    For example:
    Question: Which 3 products have the highest quantity in stock?
    SQL Query: SELECT productName, quantityInStock from products order by quantityInStock desc limit 3;
    Question: Which customers have placed orders with a total amount greater than 10,000?
    SQL Query: SELECT c.customerNumber, c.customerName, SUM(od.quantityOrdered * od.priceEach) AS totalAmount FROM customers c JOIN orders o ON c.customerNumber = o.customerNumber JOIN orderdetails od ON o.orderNumber = od.orderNumber GROUP BY c.customerNumber, c.customerName HAVING totalAmount > 10000;
    
    Your turn:
    
    Question: {question}
    SQL Query:
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    
    llm = ChatGroq(model = "llama-3.2-90b-text-preview", temperature=0)

    def get_schema(_):
        return db.get_table_info()


    return (
        RunnablePassthrough.assign(schema = get_schema)
        | prompt
        | llm
        | StrOutputParser()    
    )
    
def get_response(user_query: str, db: SQLDatabase, chat_history: list):
    sql_chain = get_sql_chain(db)
    
    template = """
    You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
    Based on the table schema below, question, sql query, and sql response, write a natural language response.
    <SCHEMA>{schema}</SCHEMA>
    
    Conversation History: {chat_history}
    SQL Query: <SQL>{query}</SQL>
    User Question: {question}
    SQL Response: {response}"""
    
    prompt = ChatPromptTemplate.from_template(template)
    
    llm = ChatGroq(model = "llama-3.2-90b-text-preview", temperature=0)
    
    chain = (
        RunnablePassthrough.assign(query=sql_chain).assign(
            schema = lambda _: db.get_table_info(),
            response = lambda vars: db.run(vars["query"],)
        )
        | prompt
        | llm
        | StrOutputParser()
    ) 
    
    return chain.invoke({
        "question":user_query,
        "chat_history":chat_history,
    })

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        AIMessage(content = "Hello! I am your assistant. Ask me anything about your Database."),
        
    ]

load_dotenv()

st.set_page_config(page_title = "CHAT WITH MYSQL", page_icon = ":speech_balloon:")
st.title("Chat with MySQL")

with st.sidebar:
    st.subheader("Settings")
    st.write("This is a simple chat application using MySQL. Connect to the database and start chatting")

    st.text_input("Host", value = "localhost", key="Host")
    st.text_input("Port",value = "3306", key= "Port")
    st.text_input("User", value = "root", key = "User")
    st.text_input("Password", type = "password", value = "root", key = "Password")
    st.text_input("Database",value="classicmodels", key = "Database")

    if st.button("connect"):
        with st.spinner("connecting to the database..."):
            db = init_database(
                st.session_state["User"],
                st.session_state["Password"],
                st.session_state["Host"],
                st.session_state["Port"],
                st.session_state["Database"]
            )
            st.session_state.db = db
            st.success("Connected to database!")


for message in st.session_state.chat_history:
    if isinstance(message, AIMessage):
        with st.chat_message("AI"):
            st.markdown(message.content)
    elif isinstance(message, HumanMessage):
        with st.chat_message("Human"):
            st.markdown(message.content)
            
user_query = st.chat_input("Type a message..")
if user_query is not None and user_query.strip() != "":
    st.session_state.chat_history.append(HumanMessage(content = user_query))
    
    with st.chat_message("Human"):
        st.markdown(user_query)
    
    
    with st.chat_message("AI"):
        response = get_response(user_query, st.session_state.db, st.session_state.chat_history)
        st.markdown(response)
        
    st.session_state.chat_history.append(AIMessage(content=response))
    
    