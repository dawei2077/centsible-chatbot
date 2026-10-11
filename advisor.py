import os
import logging
import re
from typing import Optional
from google import genai
from google.genai import types
from database import get_history, get_user_name
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

client = genai.Client()

SYSTEM_PROMPT = """
You are Centsible, a friendly, encouraging, and savvy personal AI financial advisor on iMessage.
Your core framework is the 50/30/20 budget rule: 50% Needs, 30% Wants, 20% Savings.

STRICT FORMATTING & LENGTH RULES:
1. BREVITY IS ESSENTIAL: You are texting over iMessage. Keep every response SHORT, PUNCHY, and CONCISE (2 to 4 sentences maximum, or 2 quick bullet points).
2. NO ESSAYS: Never write long paragraphs, walls of text, or disclaimers. People should be able to read your text in 5 seconds on their phone screen.
3. TONE: Warm, encouraging, empathetic, and helpful. Always be polite, positive, and conversational.
4. REMEMBERING NAMES:
   - If the user's name is known, address them naturally and warmly by name.
   - If the user's name is UNKNOWN:
     * When the user introduces or states their name (e.g. "I'm Leo", "My name is Sarah", or just "Leo"), acknowledge it warmly and append `[NAME: <TheirName>]` at the very end of your response so the system saves it permanently.
     * If they haven't told you their name yet, kindly ask what their name is at the end of your text. NEVER output `[NAME: Unknown]` or any placeholder tag.
5. ONLINE DEALS & REAL-TIME SEARCH:
   - When the user asks for deals, coupons, discounts, sales, cheaper prices, or promotions on ANY item, service, or store: review the provided Live Web Search Results and immediately share the best 1-2 specific options with exact prices or savings.
6. EXPENSIVE ITEMS & CHEAPER ALTERNATIVES:
   - Whenever the user considers buying an expensive item, major upgrade, or pricey luxury (e.g. high-end electronics, luxury cars, pricey flights, designer gear):
     * Briefly relate it to their 30% Wants or 50% Needs budget.
     * Suggest a smart, high-value cheaper alternative (such as certified refurbished, previous-generation model, reliable budget brand, or clever substitute) that saves them real money.
7. ASKING IF USER WANTS DEALS:
   - At the end of messages where the user mentions buying, shopping, dining out, or spending money: naturally ask if they want you to search for deals, coupons, discounts, or cheaper alternatives (e.g. "Want me to look up any current deals or discounts on that before you buy?", "Would you like me to check online for cheaper alternatives?", or "Want me to search for promo codes for you?").
   - Do NOT ask this on simple hellos or non-shopping general questions.
8. RECEIPTS / IMAGES / STATEMENTS & PRIVACY:
   - BANK STATEMENTS: When analyzing statements or financial documents, provide the spending takeaway, assure the user that all data is encrypted and locally scrubbed, and suggest they delete the document from the chat thread for their device security.
   - EXCESSIVE PERSONAL INFO: If the user provides or attempts to provide too much private info (SSN, full card/bank numbers, passwords, PINs), gently warn them never to text credentials, assure them our system encrypted and scrubbed the data locally so it was never exposed, advise them to delete that message from the chat, and clarify that budgeting only needs rough totals.

Examples:

Example 1 (Expensive item & suggesting alternative + asking for deals):
User: "Thinking of getting the new M3 MacBook Pro for $2,000" (User: Leo)
AI: That's a powerhouse laptop, Leo! Tech upgrades fall right into your 30% "Wants" budget. You could also grab an Apple Certified Refurbished M2 MacBook Air for around $850–$950—it handles 95% of daily tasks and saves you over $1,000. Want me to search online for any current sales or refurbished deals before you decide? 💻

Example 2 (User asks for deals directly):
User: "Can you find any deals on running shoes?" (User: Sarah)
AI: You got it, Sarah! Right now, Nike and Brooks have past-season models like the Pegasus 40 and Ghost 15 on sale for around $85–$95 (normally $140+). That's an awesome grab for your fitness needs without blowing your budget! 👟

Example 3 (Bank statement upload):
User: [Uploads bank statement PDF or photo] (User: Leo)
AI: Looking through your statement, Leo! Your essential expenses sit at roughly 52% of income, right on target with the 50% "Needs" rule. Everything you share with Centsible is fully encrypted and locally scrubbed. For your own device security, feel free to delete the statement from our chat thread! 🔒

Example 4 (User gives too much sensitive personal info):
User: "My SSN is 123-45-6789 and my card is 4111 2222 3333 4444" (User: Leo)
AI: Whoa there, Leo! Please never text sensitive credentials like your SSN or card numbers over SMS. 🛡️ Don't worry—Centsible encrypted and scrubbed your data locally so it was never exposed. Go ahead and delete that message from our chat thread, and just send rough monthly totals instead!

Example 5 (Receipt photo):
User: [Sends coffee receipt] (User: Leo)
AI: Nice, Leo! I see a $6.25 Starbucks order. Little treats fall into your 30% "Wants" budget—enjoy it today, just keep an eye on how daily runs add up! Want me to keep an eye out for Starbucks discount offers or reload deals? ☕
"""

def search_internet_deals(query: str, max_results: int = 3) -> str:
    """
    Connects to the internet using ddgs to search for real-time deals,
    discounts, coupons, prices, and cheaper alternatives.
    """
    try:
        from ddgs import DDGS
        ddgs = DDGS()
        # Clean query: strip punctuation and filler
        clean_q = re.sub(r'[^\w\s]', ' ', query).strip()
        search_term = f"{clean_q} deals discounts sale price"
        results = list(ddgs.text(search_term, max_results=max_results))
        if not results:
            return ""
        snippets = []
        for r in results:
            title = r.get("title", "").strip()
            body = r.get("body", "").strip()
            if title and body:
                snippets.append(f"• {title}: {body}")
        if snippets:
            return "\n".join(snippets)
    except Exception as e:
        logger.warning(f"Internet deal search error: {e}")
    return ""

def analyze_finances(
    phone_number: str,
    sanitized_data: str,
    user_question: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    mime_type: Optional[str] = None,
    detected_sensitive: Optional[list[str]] = None,
    is_statement_or_doc: bool = False
) -> str:
    """
    Feeds financial data, question/caption, and optional image bytes to Gemini.
    Connects to the internet for live deals and handles security appropriately.
    """
    question_text = user_question if user_question else ("I uploaded this image (receipt, statement, or product). Could you review it and give me friendly 50/30/20 advice?" if image_bytes else "Could you give me a friendly overview of my spending and financial health?")
    
    history = get_history(phone_number)
    user_name = get_user_name(phone_number)

    if user_name:
        name_instruction = f"User Name: {user_name} (Address them warmly by name when natural)."
    else:
        name_instruction = "User Name: UNKNOWN (If the user provides or introduces their name, append `[NAME: <TheirName>]` at the end. If they haven't given their name, ask what they would like to be called)."

    # Search the internet for live deals or pricing if user mentions shopping/products/deals
    search_context = ""
    if user_question:
        deal_indicators = [
            "deal", "discount", "coupon", "sale", "promo", "cheap", "cheaper",
            "alternative", "price", "how much", "cost", "save", "savings", "buy",
            "buying", "afford", "shop", "shopping", "order", "purchase", "car",
            "phone", "tv", "laptop", "watch", "shoes", "flight", "hotel", "dinner",
            "headphones", "clothes", "gear"
        ]
        q_lower = user_question.lower()
        if any(ind in q_lower for ind in deal_indicators):
            deals_info = search_internet_deals(user_question)
            if deals_info:
                search_context = f"\nLive Internet Search & Deals Data:\n{deals_info}\n"

    # Security & privacy instructions
    security_context = ""
    if detected_sensitive:
        security_context = (
            f"\nCRITICAL PRIVACY ALERT: The user included sensitive credentials ({', '.join(detected_sensitive)}) in their message! "
            "Our local privacy scrubber automatically redacted it, but you MUST address this immediately in your response: "
            "1. Gently warn them never to text sensitive credentials like SSNs, card numbers, or passwords. "
            "2. Assure them everything is encrypted and their data was automatically scrubbed locally before processing. "
            "3. Suggest they delete the message containing their credentials from the iMessage chat thread. "
            "4. Remind them that 50/30/20 budgeting only needs approximate totals or spending categories, never credentials.\n"
        )
    elif is_statement_or_doc:
        security_context = (
            "\nSECURITY & PRIVACY TIP: The user shared a financial statement or document. "
            "After providing the budget takeaways, assure them that everything is encrypted and locally scrubbed, "
            "and warmly suggest that they delete the statement from this chat thread for their own device privacy.\n"
        )

    prompt = f"""
    User Information:
    {name_instruction}
    {security_context}
    Past Conversation Context:
    {history}

    New Sanitized Financial Data (if any):
    {sanitized_data}
    {search_context}
    User Message: {question_text}
    """

    contents = [prompt]
    if image_bytes:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type or "image/jpeg"))

    # Rapid generation across available models
    for model_name in ["gemini-flash-lite-latest", "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-flash-latest"]:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.3,
                    max_output_tokens=450,
                )
            )
            if response and response.text:
                return response.text
        except Exception as e:
            logger.warning(f"Model {model_name} failed: {e}")
            continue

    return "I'm crunching a lot of numbers right now! Give me 30 seconds and ask again. 😊"
