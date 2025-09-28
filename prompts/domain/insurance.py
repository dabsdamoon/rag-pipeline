INSURANCE_PROMPT = """
Now, you will be given contexts regarding how to take care of insurance claims with company {company_name}.
Please provide answer in {language} for this insurance-related inquiry with the following context guidelines:

# Guidelines:
- You can use your own knowledge to answer the question, but if so, say it clearly.
- Do not have to provide full-detailed answer, just provide concise and relevant information.
- When explaining steps, use bullet points or numbered lists for clarity.
- If unsure, recommend consulting with insurance providers for specific policy details
- Even context is in different language, answer in {language}.

# Common acronyms
- GOP: Guarantee of Payments
- EOB: Explanation of Benefits

# Context:
{context}
"""
