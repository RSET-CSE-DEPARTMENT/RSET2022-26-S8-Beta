from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# -------- LOCAL OLLAMA MODEL --------
llm = ChatOllama(
    model="llama3",
    temperature=0.2,
)

# -------- MAIN PROMPT --------
SYSTEM_PROMPT = """
You are a Cyber Threat Intelligence Analyst.

Analyze dark web content related to an organization.

Give structured output:

1. Short Summary (2 lines)
2. Threat Type (leak/marketplace/ransomware/forum/scam/benign)
3. Risk Level (CRITICAL/HIGH/MEDIUM/LOW)
4. Key Indicators (emails, passwords, wallets, leaks)
5. Key Insights (3 bullet points)
Be concise and technical.
"""

# -------- MAIN FUNCTION --------
def analyze_darkweb_content(query, content):

    if not content or len(content) < 200:
        return "No meaningful content"

    content = content[:2500]  # prevent slow LLM

    prompt_template = ChatPromptTemplate(
        [("system", SYSTEM_PROMPT), ("user", "{content}")]
    )

    chain = prompt_template | llm | StrOutputParser()

    try:
        result = chain.invoke({
            "query": query,
            "content": content
        })
        return result

    except Exception as e:
        print("LLM ERROR:", e)
        return "LLM analysis failed"