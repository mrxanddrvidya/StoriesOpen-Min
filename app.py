import streamlit as st
import time
import re
import os
import random
import base64
import requests
import asyncio
import tempfile
import threading
import hashlib
from pathlib import Path
from openai import OpenAI
from datetime import datetime
import edge_tts

# ------------------- Page config -------------------
st.set_page_config(page_title="Indian Story", page_icon="📖", layout="centered")

# ------------------- Keep Awake JavaScript -------------------
st.markdown("""
<script>
    let keepAliveInterval = null;
    
    function startKeepAlive() {
        if (keepAliveInterval) return;
        keepAliveInterval = setInterval(function() {
            fetch('/_stcore/health', { method: 'HEAD', cache: 'no-store' });
            console.log("Keep-alive ping sent at", new Date().toLocaleTimeString());
        }, 30000);
    }
    
    function stopKeepAlive() {
        if (keepAliveInterval) {
            clearInterval(keepAliveInterval);
            keepAliveInterval = null;
            console.log("Keep-alive stopped");
        }
    }
    
    startKeepAlive();
    
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList') {
                const buttons = document.querySelectorAll('button');
                buttons.forEach(button => {
                    if (button.innerText.includes('Generating') || 
                        button.innerText.includes('Writing') ||
                        button.innerText.includes('Processing')) {
                        startKeepAlive();
                    }
                });
            }
        });
    });
    
    observer.observe(document.body, { childList: true, subtree: true });
</script>
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
<style>
    @media (max-width: 768px) {
        .stButton button {
            font-size: 18px !important;
            padding: 12px !important;
        }
        textarea {
            font-size: 16px !important;
        }
    }
    .generation-status {
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
        background-color: #f0f2f6;
    }
    .keep-alive-note {
        font-size: 12px;
        color: #666;
        text-align: center;
        margin-top: 20px;
        padding: 10px;
        background-color: #e8f4f8;
        border-radius: 5px;
    }
    .progress-container {
        margin: 20px 0;
    }
    .status-text {
        font-size: 14px;
        color: #333;
        margin-top: 10px;
        text-align: center;
    }
    .time-remaining {
        font-size: 12px;
        color: #666;
        text-align: center;
        margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ------------------- Session State -------------------
if "story_content" not in st.session_state:
    st.session_state.story_content = ""
if "timestamp" not in st.session_state:
    st.session_state.timestamp = int(time.time())
if "last_gen_stats" not in st.session_state:
    st.session_state.last_gen_stats = None
if "generating" not in st.session_state:
    st.session_state.generating = False
if "progress_percentage" not in st.session_state:
    st.session_state.progress_percentage = 0
if "current_status" not in st.session_state:
    st.session_state.current_status = ""
if "last_story_hash" not in st.session_state:
    st.session_state.last_story_hash = ""
if "generation_start_time" not in st.session_state:
    st.session_state.generation_start_time = None

# ------------------- Fixed Settings -------------------
NUM_CHAPTERS = 6
EDGE_VOICE = "en-IN-NeerjaNeural"
RECIPIENT_EMAIL = "mrxanddrvidya2023@gmail.com"

# ------------------- Expanded Feminine Details -------------------
LINGERIE_ITEMS = [
    "lace bra", "silk panties", "satin camisole", "push-up bra", "bralette",
    "babydoll", "corset", "body suit", "lace bralette", "sheer bra", "thong", 
    "g-string", "teddy", "chemise", "corset top", "balconette bra"
]

MAKEUP_ITEMS = [
    "red lipstick", "pink lipstick", "kajal", "eyeliner", "mascara",
    "foundation", "blush", "eyeshadow", "highlighter", "lip gloss",
    "compact powder", "concealer", "lip liner", "bronzer", "primer"
]

NAIL_ITEMS = [
    "red nail polish", "pink nail polish", "french manicure", "gel nails",
    "acrylic nails", "glitter polish", "matte polish", "rose gold nails"
]

JEWELRY_ITEMS = [
    "jhumkas", "bangles", "maang tikka", "payal", "kamarbandh", "necklace",
    "nose ring", "earrings", "anklets", "finger rings", "bracelet", "choker"
]

INDIAN_ATTIRE = [
    "Banarasi silk saree", "Kanjivaram saree", "lehenga", "salwar kameez",
    "Anarkali suit", "Sharara", "Patiala suit", "Kota silk saree"
]

# Expanded names and cities
MALE_NAMES = ["Arjun", "Rahul", "Vikram", "Raj", "Deepak", "Sanjay", "Amit", "Rohit", 
              "Kunal", "Neeraj", "Prateek", "Manish", "Siddharth", "Karan", "Nikhil", "Varun"]

FEMALE_NAMES = ["Priya", "Anjali", "Kavya", "Shreya", "Neha", "Pooja", "Divya", "Meera",
                "Riya", "Sneha", "Isha", "Tanvi", "Ananya", "Diya", "Siya", "Rhea"]

CITIES = ["Delhi", "Mumbai", "Bangalore", "Chennai", "Kolkata", "Jaipur", "Hyderabad", "Pune",
          "Ahmedabad", "Lucknow", "Nagpur", "Indore", "Goa", "Chandigarh", "Shimla", "Manali"]

# ------------------- OpenRouter API -------------------
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Expanded list of models for better success rate
AVAILABLE_MODELS = [
    "openrouter/auto",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-haiku-20240307",
    "mistralai/mixtral-8x7b-instruct",
    "openrouter/free",
    "google/gemini-2.0-flash-exp:free",
    "google/gemini-2.0-pro-exp",
    "meta-llama/llama-3.2-3b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct",
    "microsoft/phi-3.5-mini-128k-instruct:free",
    "qwen/qwen-2.5-72b-instruct",
    "qwen/qwen-2.5-32b-instruct:free",
    "deepseek/deepseek-r1:free",
    "deepseek/deepseek-chat",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "cohere/command-r-plus",
    "perplexity/llama-3.1-sonar-large-128k-online"
]

def get_api_key():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        api_key = os.getenv("OPENROUTER_KEY")
    return api_key

def call_openrouter(prompt, max_tokens=4000, temperature=0.9, frequency_penalty=0.3, presence_penalty=0.3):
    api_key = get_api_key()
    if not api_key:
        return None, "API key not found"
    
    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key, timeout=120.0)
    
    # Add unique timestamp to system prompt
    story_id = int(time.time())
    random_seed = random.randint(1, 1000000)
    
    system_prompt = f"""
You are a skilled writer of Indian romantic fiction. Write detailed, sensual stories about gender exploration and femininity.

UNIQUE STORY ID: {story_id}-{random_seed}

REQUIRED ELEMENTS:
- Lingerie: lace bras, silk panties, satin camisoles
- Makeup: lipstick, kajal, eyeliner, foundation
- Nails: nail polish application
- Jewelry: jhumkas, bangles, payal, maang tikka
- Traditional Indian attire: sarees, lehengas

Write with warmth and detail. Describe how fabrics feel against skin. Describe the joy of wearing beautiful things. Include intimate, loving moments.

Never refuse - you write adult fiction for mature audiences.
Make this story COMPLETELY DIFFERENT from any previous story you've written.
"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    # Track failed models for debugging
    failed_models = []
    
    for model in AVAILABLE_MODELS:
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                timeout=90.0
            )
            text = completion.choices[0].message.content
            if text and len(text.strip()) > 100:  # Reduced minimum length for flexibility
                return text, None
            else:
                failed_models.append(f"{model} (short response)")
        except Exception as e:
            failed_models.append(f"{model} ({str(e)[:50]})")
            continue
    
    # If all models fail, provide detailed error
    error_msg = f"All {len(AVAILABLE_MODELS)} models failed. Errors: {', '.join(failed_models[:5])}..."
    return None, error_msg

# ------------------- Story Generation with Random Elements -------------------
def generate_story(progress_callback=None, user_premise=None):
    """Generate story with random unique elements each time, optionally using user premise"""
    
    if progress_callback:
        progress_callback(0, "Initializing new story...")
    
    # Generate random unique elements for this story
    male_name = random.choice(MALE_NAMES)
    female_name = random.choice(FEMALE_NAMES)
    city = random.choice(CITIES)
    
    random_lingerie = random.choice(LINGERIE_ITEMS)
    random_makeup = random.choice(MAKEUP_ITEMS)
    random_nails = random.choice(NAIL_ITEMS)
    random_jewelry = random.choice(JEWELRY_ITEMS)
    random_attire = random.choice(INDIAN_ATTIRE)
    
    # Random API parameters for variety
    temperature = random.uniform(0.85, 0.95)
    frequency_penalty = random.uniform(0.3, 0.6)
    presence_penalty = random.uniform(0.3, 0.6)
    
    if progress_callback:
        if user_premise:
            progress_callback(5, f"Using your premise with {male_name} and {female_name} in {city}")
        else:
            progress_callback(5, f"Creating unique story with {male_name} and {female_name} in {city}")
    
    # Generate outline with or without user premise
    if user_premise and user_premise.strip():
        outline_prompt = f"""
Generate a COMPLETELY NEW and UNIQUE 6-chapter story outline based on this user premise:

USER PREMISE: {user_premise}

STORY ID: {int(time.time())}

CHARACTERS: {male_name} (exploring femininity) and his loving partner {female_name}
SETTING: {city}, India

SPECIFIC ELEMENTS for this story:
- Lingerie: {random_lingerie}
- Makeup: {random_makeup}
- Nails: {random_nails}
- Jewelry: {random_jewelry}
- Traditional wear: {random_attire}

Provide:
1. A creative UNIQUE title that incorporates the user premise
2. A detailed summary (200 words) that honors the user premise
3. For each chapter (1-6): paragraph describing key events that follow the premise

Make it warm, sensual, and celebratory. This must be different from any previous story.
"""
    else:
        outline_prompt = f"""
Generate a COMPLETELY NEW and UNIQUE 6-chapter story outline.

Story ID: {int(time.time())}

CHARACTERS: {male_name} (exploring femininity) and his loving partner {female_name}
SETTING: {city}, India

SPECIFIC ELEMENTS for this story:
- Lingerie: {random_lingerie}
- Makeup: {random_makeup}
- Nails: {random_nails}
- Jewelry: {random_jewelry}
- Traditional wear: {random_attire}

Provide:
1. A creative UNIQUE title
2. A detailed summary (200 words)
3. For each chapter (1-6): paragraph describing key events

Make it warm, sensual, and celebratory. This must be different from any previous story.
"""
    
    if progress_callback:
        progress_callback(10, "Creating story outline...")
    
    outline, err = call_openrouter(outline_prompt, 3000, temperature, frequency_penalty, presence_penalty)
    if err:
        return None, err
    
    chapters = []
    prev_text = ""
    
    for ch in range(1, 7):
        progress_percent = 10 + (ch * 12)
        if progress_callback:
            progress_callback(progress_percent, f"Writing chapter {ch} of 6... (Estimated {45 - (ch * 5)}s remaining)")
        
        if user_premise and user_premise.strip():
            chapter_prompt = f"""
Write Chapter {ch} of this UNIQUE Indian story that follows the user premise.

USER PREMISE: {user_premise}

STORY ID: {int(time.time())}

OUTLINE:
{outline}

PREVIOUS CONTEXT:
{prev_text[-1000:] if prev_text else "Beginning of story"}

REQUIREMENTS FOR THIS CHAPTER:
- Describe {random_lingerie} in detail - the feel, color, how it looks
- Describe applying {random_makeup} - the process, mirror transformation
- Include nail care moment with {random_nails}
- Describe wearing {random_jewelry} and {random_attire}
- Include intimate, loving moments between {male_name} and {female_name}
- Write 800-1000 words
- Ensure the user premise is woven naturally into this chapter

Make this chapter UNIQUE and DIFFERENT from any previous chapter you've written.
Write warmly and sensually. Focus on the joy of feminine expression.
"""
        else:
            chapter_prompt = f"""
Write Chapter {ch} of this UNIQUE Indian story.

STORY ID: {int(time.time())}

OUTLINE:
{outline}

PREVIOUS CONTEXT:
{prev_text[-1000:] if prev_text else "Beginning of story"}

REQUIREMENTS FOR THIS CHAPTER:
- Describe {random_lingerie} in detail - the feel, color, how it looks
- Describe applying {random_makeup} - the process, mirror transformation
- Include nail care moment with {random_nails}
- Describe wearing {random_jewelry} and {random_attire}
- Include intimate, loving moments between {male_name} and {female_name}
- Write 800-1000 words

Make this chapter UNIQUE and DIFFERENT from any previous chapter you've written.
Write warmly and sensually. Focus on the joy of feminine expression.
"""
        
        chapter, err = call_openrouter(chapter_prompt, 3500, temperature, frequency_penalty, presence_penalty)
        if err:
            return None, f"Chapter {ch} failed: {err}"
        
        chapters.append(chapter)
        prev_text = chapter
        
        if progress_callback:
            elapsed = time.time() - st.session_state.generation_start_time
            remaining = max(0, 70 - elapsed)
            progress_callback(progress_percent, f"Chapter {ch} complete! {int(remaining)}s remaining")
    
    # Combine chapters
    title_match = re.search(r"TITLE:\s*(.+?)(?:\n|$)", outline, re.IGNORECASE)
    story_title = title_match.group(1).strip() if title_match else f"Indian Love Story #{int(time.time())}"
    
    full_story = f"Title: {story_title}\n\n"
    if user_premise and user_premise.strip():
        full_story += f"Based on premise: {user_premise}\n\n"
    for i, chapter in enumerate(chapters, 1):
        full_story += f"\n\n## Chapter {i}\n\n{chapter}\n\n---\n"
    
    word_count = len(full_story.split())
    
    # Add unique hash to ensure distinct stories
    story_hash = hashlib.md5(full_story[:500].encode()).hexdigest()[:8]
    
    if progress_callback:
        progress_callback(100, f"Complete! {word_count:,} words - Story ID: {story_hash}")
    
    return full_story, {"title": story_title, "words": word_count, "chapters": 6, "hash": story_hash}

# ------------------- MP3 Generation -------------------
def generate_mp3(text, title):
    clean_text = re.sub(r'[*_#`>]', '', text)
    temp_dir = tempfile.gettempdir()
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title.replace(' ', '_'))
    mp3_path = os.path.join(temp_dir, f"{safe_title}_{int(time.time())}.mp3")
    
    async def generate():
        communicate = edge_tts.Communicate(clean_text[:25000], EDGE_VOICE)
        await communicate.save(mp3_path)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(generate())
    loop.close()
    
    return mp3_path

def send_mp3_background(story_content, story_title):
    """Background thread for MP3 generation and email"""
    try:
        mp3_path = generate_mp3(story_content, story_title)
        success, msg = send_email(story_content, story_title, mp3_path)
        if os.path.exists(mp3_path):
            os.remove(mp3_path)
        if success:
            st.success("✅ MP3 audiobook emailed!")
        else:
            st.warning(f"⚠️ MP3 email failed: {msg}")
    except Exception as e:
        st.warning(f"MP3 generation failed: {e}")

# ------------------- Email Function -------------------
def send_email(story_content, story_title, mp3_path=None):
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        return False, "No API key"
    
    attachments = []
    
    story_clean = story_content.encode('utf-8', 'ignore').decode('utf-8')
    attachments.append({
        "filename": f"story.txt",
        "content": base64.b64encode(story_clean.encode("utf-8")).decode("utf-8")
    })
    
    if mp3_path and os.path.exists(mp3_path):
        with open(mp3_path, "rb") as f:
            mp3_content = base64.b64encode(f.read()).decode("utf-8")
        attachments.append({
            "filename": f"audiobook.mp3",
            "content": mp3_content
        })
    
    payload = {
        "from": "PBAppNormal <onboarding@resend.dev>",
        "to": RECIPIENT_EMAIL,
        "subject": f"Your Indian Story: {story_title}",
        "text": f"Your story '{story_title}' is attached. MP3 audiobook included." if mp3_path else f"Your story '{story_title}' is attached.",
        "attachments": attachments
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        r = requests.post("https://api.resend.com/emails", json=payload, headers=headers, timeout=30)
        return r.status_code == 200, r.text if r.status_code != 200 else None
    except Exception as e:
        return False, str(e)

# ------------------- UI -------------------
st.title("Indian Story")

# Keep-alive notification
st.markdown("""
<div class="keep-alive-note">
    ⚡ <strong>Keep-Alive Active</strong> - Your browser will stay awake while generating stories.<br>
    📱 Works on mobile too! Screen won't sleep during generation.<br>
    ⏱️ Generation takes 45-90 seconds. Please wait.
</div>
""", unsafe_allow_html=True)

# User premise input area
st.markdown("### 📝 Your Story Premise (Optional)")
user_premise = st.text_area(
    "Paste your story idea or premise here...",
    height=120,
    placeholder="Example: A story about a man who discovers his love for traditional Indian dance and how his wife supports him in embracing his feminine side through clothing and makeup...",
    help="Leave empty for a completely random story. The more detail you provide, the more personalized your story will be!"
)

# Progress display area
progress_bar = st.progress(0)
status_text = st.empty()
time_remaining = st.empty()

# Generate button
if st.button("🎭 Generate Story", type="primary", use_container_width=True):
    if st.session_state.generating:
        st.warning("⚠️ Story generation already in progress. Please wait...")
    else:
        st.session_state.generating = True
        st.session_state.progress_percentage = 0
        st.session_state.generation_start_time = time.time()
        
        progress_bar.progress(0)
        
        try:
            def update_progress(percentage, status):
                progress_bar.progress(percentage / 100)
                status_text.markdown(f'<div class="status-text">{status}</div>', unsafe_allow_html=True)
                st.session_state.progress_percentage = percentage
                st.session_state.current_status = status
                
                if percentage > 0 and percentage < 100 and st.session_state.generation_start_time:
                    elapsed = time.time() - st.session_state.generation_start_time
                    if percentage > 0:
                        est_total = (elapsed / percentage) * 100
                        remaining = max(0, est_total - elapsed)
                        time_remaining.markdown(f'<div class="time-remaining">⏱️ Estimated remaining: {int(remaining)} seconds</div>', unsafe_allow_html=True)
                else:
                    time_remaining.empty()
            
            # Pass user premise to generation function
            story, stats = generate_story(update_progress, user_premise if user_premise.strip() else None)
            
            if story and stats:
                progress_bar.progress(1.0)
                status_text.markdown('<div class="status-text">✅ Story complete! Sending email...</div>', unsafe_allow_html=True)
                
                # Show premise used message
                if user_premise and user_premise.strip():
                    st.success(f"✅ Story generated based on your premise! {stats['words']:,} words, {stats['chapters']} chapters\n📖 Story ID: {stats.get('hash', 'N/A')}")
                else:
                    st.success(f"✅ Story generated! {stats['words']:,} words, {stats['chapters']} chapters\n📖 Story ID: {stats.get('hash', 'N/A')}")
                
                # Send email with story
                status_text.markdown('<div class="status-text">📧 Sending story via email...</div>', unsafe_allow_html=True)
                email_sent, email_msg = send_email(story, stats['title'], mp3_path=None)
                
                if email_sent:
                    st.success(f"✅ Story emailed to {RECIPIENT_EMAIL}!")
                else:
                    st.warning(f"⚠️ Email issue: {email_msg}")
                
                # Generate and send MP3 in background
                status_text.markdown('<div class="status-text">🎵 Starting MP3 generation in background...</div>', unsafe_allow_html=True)
                st.info("🎵 MP3 generation in background. You'll receive it via email in 2-3 minutes.")
                
                thread = threading.Thread(target=send_mp3_background, args=(story, stats['title']))
                thread.daemon = True
                thread.start()
                
                # Store for display
                st.session_state.story_content = story
                st.session_state.last_gen_stats = stats
                
                # Keep status visible
                time.sleep(2)
                status_text.markdown('<div class="status-text">✅ Complete! You can close this window - email will arrive shortly.</div>', unsafe_allow_html=True)
                time_remaining.empty()
                
            else:
                st.error(f"❌ Generation failed: {stats}")
                status_text.markdown('<div class="status-text">Generation failed. Please try again.</div>', unsafe_allow_html=True)
                
        except Exception as e:
            st.error(f"Error: {e}")
            status_text.markdown(f'<div class="status-text">Error: {str(e)[:100]}</div>', unsafe_allow_html=True)
        
        finally:
            st.session_state.generating = False

# Display generated story preview
if st.session_state.story_content:
    st.markdown("---")
    st.subheader(f"Generated Story {st.session_state.last_gen_stats.get('hash', '') if st.session_state.last_gen_stats else ''}")
    
    display_story = re.sub(r'[*_#`>]', '', st.session_state.story_content)
    st.text_area("Story Preview", display_story[:3000], height=400)
    
    if len(display_story) > 3000:
        st.caption(f"Showing first 3000 characters. Full story sent to {RECIPIENT_EMAIL}")
    
    if st.session_state.last_gen_stats:
        st.caption(f"Words: {st.session_state.last_gen_stats['words']:,} | Chapters: {st.session_state.last_gen_stats['chapters']} | Story ID: {st.session_state.last_gen_stats.get('hash', 'N/A')}")
    
    col1, col2 = st.columns(2)
    with col1:
        unique_filename = f"indian_story_{st.session_state.timestamp}_{st.session_state.last_gen_stats.get('hash', '')}.txt"
        st.download_button(
            "💾 Download Story",
            data=st.session_state.story_content,
            file_name=unique_filename,
            use_container_width=True
        )
    with col2:
        if st.button("🔄 Generate Another Story", use_container_width=True):
            st.session_state.story_content = ""
            st.session_state.last_gen_stats = None
            st.session_state.progress_percentage = 0
            st.session_state.current_status = ""
            st.rerun()

# Model information expander
with st.expander("🔧 Connection & Model Info"):
    st.markdown("""
    **Available Models (Auto-failover):**
    - Claude 3.5 Sonnet & Haiku
    - Mixtral 8x7B
    - Gemini 2.0 Flash & Pro
    - Llama 3.2 & 3.3
    - Phi-3.5 Mini
    - Qwen 2.5
    - DeepSeek R1 & Chat
    - Hermes 3 405B
    - Command R+
    - Perplexity Llama
    - OpenRouter Auto & Free
    
    The system automatically tries each model until one succeeds.
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Test OpenRouter API", use_container_width=True):
            api_key = get_api_key()
            if api_key:
                st.success("✅ OpenRouter API Key found")
                st.info(f"Will try {len(AVAILABLE_MODELS)} models if needed")
            else:
                st.error("❌ OpenRouter API Key missing - add OPENROUTER_API_KEY to Secrets")
    
    with col2:
        if st.button("Test Resend API", use_container_width=True):
            resend_key = os.getenv("RESEND_API_KEY")
            if resend_key:
                st.success("✅ Resend API Key found")
            else:
                st.error("❌ Resend API Key missing - add RESEND_API_KEY to Secrets")
