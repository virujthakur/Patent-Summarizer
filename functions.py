import requests
import fitz  # PyMuPDF

def download_pdf(url, filename):
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    with open(filename, "wb") as f:
        f.write(response.content)

def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def chat_ollama(messages, model="llama3:8b"):
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9
            }
        },
        timeout=180
    )
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]

def summarize_text(text):
    system_rules = """
You are a patent analyst.
Write exactly one paragraph with 6 to 8 sentences.
Cover:
1. Problem in prior art
2. Core solution and mechanism
3. Main advantage over prior art
Use clear, non-jargon language where possible.
Do not use headings or bullet points.
"""

    example_output = """
This invention addresses discomfort and performance issues caused by the initial intensity spike in IPL light pulses. Prior designs used bulky inductors to smooth current, increasing cost and size. The invention places an electronic switch in series with the lamp and controls it at high frequency to shape current delivery. By rapidly toggling the switch, the controller converts the spike into a more uniform block-like pulse. This provides more stable light output while preserving treatment effectiveness. It also reduces component size and complexity compared with inductor-heavy designs.
"""

    messages = [
        {"role": "system", "content": system_rules},
        {"role": "assistant", "content": example_output},
        {
            "role": "user",
            "content": (
                "Summarize the following patent in the same style and format.\n\n"
                f"Patent text:\n{text}"
            ),
        },
    ]

    return chat_ollama(messages)

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

def get_pdf_link(url):
    options = Options()
    options.add_argument("--headless=new")  # run without opening browser

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    time.sleep(3)  # wait for page to load JS

    links = driver.find_elements(By.XPATH, "//a")

    for link in links:
        text = link.text.lower()
        href = link.get_attribute("href")

        if href and "pdf" in (text + href).lower():
            return href

    # Step 2: fallback to click
    button = driver.find_element(By.XPATH, "//*[contains(., 'PDF')]")
    button.click()

    driver.switch_to.window(driver.window_handles[-1])
    driver.quit()

    pdf_url = driver.current_url

    return pdf_url