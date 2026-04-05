from langchain_ollama import ChatOllama

llm = ChatOllama(model="phi3", temperature=0.2)

def generate_org_report(org_name, pages):

    if not pages:
        return "No data found"

    combined = "\n\n".join(pages)[:6000]

    prompt = f"""
You are a senior cyber threat intelligence analyst.

Analyze dark web data related to {org_name}.

Give a professional threat report:

1. Executive summary (2-3 lines)
2. Most dangerous findings
3. What type of threats detected
4. Is organization at risk?
5. Final risk level: CRITICAL/HIGH/MEDIUM/LOW
6. Recommended actions

Data:
{combined}
"""

    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        print("LLM error:", e)
        return "Report generation failed"