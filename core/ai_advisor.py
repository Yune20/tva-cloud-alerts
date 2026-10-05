"""
AI Chart Advisor — compact prompt for fast Ollama response.
"""
import json
import re
import httpx


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"


def _build_prompt(symbol, signals, psychology, darvas, structure, mtf_consensus, entry_exit):
    """Ultra-compact prompt for fast response."""
    ee = entry_exit or {}
    sig = signals or {}
    psych = psychology or {}
    darv = darvas or {}
    mtf = mtf_consensus or {}

    rsi = sig.get("RSI", {})
    macd = sig.get("MACD", {})
    adx = sig.get("ADX", {})
    stoch = sig.get("Stochastic", {})

    prompt = f"""Trade {symbol}. Price={ee.get('last_price',0):.2f}. S={ee.get('nearest_support','?')} R={ee.get('nearest_resistance','?')}. RSI={rsi.get('value','?')}({rsi.get('signal','?')}). MACD={macd.get('direction','?')}. ADX={adx.get('value','?')}. Psych={psych.get('zone','?')} {psych.get('score',0)}/100. Darvas={darv.get('trend','?')}. MTF={mtf.get('direction','?')}.

JSON only:
{{"direction":"LONG/SHORT/STAND_ASIDE","entry":number,"sl":number,"tp1":number,"tp2":number,"rr":"ratio","reason":"one line"}}"""

    return prompt


def ask_ollama(prompt, model=None, timeout=120):
    """Send prompt to Ollama and return the response text."""
    model = model or MODEL
    try:
        resp = httpx.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 300,
                },
            },
            timeout=timeout,
        )
        data = resp.json()
        text = data.get("response", "")
        if not text:
            text = data.get("thinking", "")
        return text
    except Exception as e:
        return f"Error: {e}"


def _parse_json_response(text):
    """Extract JSON from LLM response."""
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if m:
        text = m.group(1)
    m = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def analyze(symbol, df, signals=None, psychology=None, darvas=None, structure=None, mtf_consensus=None, entry_exit=None):
    """Main entry: send compact data to Ollama and get trading advice."""
    prompt = _build_prompt(symbol, signals, psychology, darvas, structure, mtf_consensus, entry_exit)
    raw = ask_ollama(prompt)

    if not raw or raw.startswith("Error"):
        return {"raw": raw or "No response", "parsed": None, "error": True}

    parsed = _parse_json_response(raw)

    return {
        "raw": raw,
        "parsed": parsed,
        "model": MODEL,
        "error": False,
    }
