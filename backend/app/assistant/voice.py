"""Voice assistant helpers: intent detection in 6 languages, translated speakable templates, markdown stripping.

Used by /assistant/chat when `language` / `voice` are sent. Deterministic, so it works without an LLM key.
Every answer is built only from the user's own records (the `ctx` dict from assistant.router.context).
"""

import re

LANGS = ("en", "hi", "te", "ta", "kn", "ml")
LANG_NAMES = {"en": "English", "hi": "Hindi", "te": "Telugu", "ta": "Tamil", "kn": "Kannada", "ml": "Malayalam"}

# Order matters: the first intent whose keywords match wins (interviews before jobs: "job interview").
INTENT_WORDS: dict[str, tuple[str, ...]] = {
    "interviews": ("interview", "इंटरव्यू", "साक्षात्कार", "ఇంటర్వ్యూ", "నేర్కాణల్", "நேர்காணல்", "இன்டர்வியூ", "ಸಂದರ್ಶನ", "ಇಂಟರ್ವ್ಯೂ",
                   "ഇന്റർവ്യൂ", "അഭിമുഖ"),
    "followups": ("follow-up", "follow up", "followup", "फॉलो", "ఫాలో", "ஃபாலோ", "ಫಾಲೋ", "ഫോളോ"),
    "emails": ("email", "mail", "inbox", "repl", "ईमेल", "मेल", "जवाब", "ఈమెయిల్", "మెయిల్", "సమాధాన", "மின்னஞ்சல்", "மெயில்", "பதில்",
               "ಇಮೇಲ್", "ಮೇಲ್", "ಉತ್ತರ", "ഇമെയിൽ", "മെയിൽ", "മറുപടി"),
    "applications": ("application", "applied", "pipeline", "status", "आवेदन", "अप्लाई", "దరఖాస్తు", "అప్లై", "விண்ணப்ப", "அப்ளை",
                     "ಅರ್ಜಿ", "ಅಪ್ಲೈ", "അപേക്ഷ", "അപ്ലൈ"),
    "profile": ("resume", " cv", "profile", "score", "tips", "रिज़्यूमे", "रिज्यूमे", "प्रोफ़ाइल", "प्रोफाइल", "రెజ్యూమే", "ప్రొఫైల్",
                "ரெஸ்யூம்", "சுயவிவர", "ರೆಸ್ಯೂಮ್", "ಪ್ರೊಫೈಲ್", "റെസ്യൂമെ", "പ്രൊഫൈൽ"),
    "jobs": ("job", "match", "opening", "vacanc", "नौकरी", "नौकरियां", "नौकरियाँ", "जॉब", "ఉద్యోగ", "జాబ్", "வேலை", "ஜாப்", "ಉದ್ಯೋಗ",
             "ಕೆಲಸ", "ಜಾಬ್", "ജോലി", "ജോബ്"),
    "help": ("help", "what can you", "मदद", "सहायता", "సహాయం", "உதவி", "ಸಹಾಯ", "സഹായ"),
}


def detect_intent(text: str) -> str | None:
    t = text.lower()
    for intent, words in INTENT_WORDS.items():
        if any(w in t for w in words):
            return intent
    return None


# Templates: {placeholders} filled from records. Order per key: en, hi, te, ta, kn, ml.
T: dict[str, tuple[str, str, str, str, str, str]] = {
    "jobs": ("You have {n} matching jobs. Top ones: {top}.",
             "आपके लिए {n} मिलती-जुलती नौकरियाँ हैं। सबसे अच्छी: {top}।",
             "మీకు {n} సరిపోయే ఉద్యోగాలు ఉన్నాయి. ముఖ్యమైనవి: {top}.",
             "உங்களுக்கு {n} பொருத்தமான வேலைகள் உள்ளன. சிறந்தவை: {top}.",
             "ನಿಮಗೆ {n} ಹೊಂದುವ ಉದ್ಯೋಗಗಳಿವೆ. ಉತ್ತಮವಾದವು: {top}.",
             "നിങ്ങൾക്ക് {n} യോജിക്കുന്ന ജോലികളുണ്ട്. മികച്ചവ: {top}."),
    "jobs_none": ("No new job matches yet. Open Jobs for you to refresh the feed.",
                  "अभी कोई नई नौकरी नहीं मिली। फ़ीड रीफ़्रेश करने के लिए जॉब्स खोलें।",
                  "ఇంకా కొత్త ఉద్యోగాలు లేవు. ఫీడ్ రిఫ్రెష్ చేయడానికి జాబ్స్ తెరవండి.",
                  "இன்னும் புதிய வேலைகள் இல்லை. புதுப்பிக்க வேலைகள் பக்கத்தைத் திறக்கவும்.",
                  "ಇನ್ನೂ ಹೊಸ ಉದ್ಯೋಗಗಳಿಲ್ಲ. ರಿಫ್ರೆಶ್ ಮಾಡಲು ಜಾಬ್ಸ್ ತೆರೆಯಿರಿ.",
                  "ഇതുവരെ പുതിയ ജോലികളില്ല. പുതുക്കാൻ ജോബ്സ് തുറക്കുക."),
    "at": ("{title} at {company}", "{company} में {title}", "{company}లో {title}", "{company} இல் {title}", "{company} ನಲ್ಲಿ {title}",
           "{company} ൽ {title}"),
    "apps": ("You have {n} applications: {stages}.", "आपके {n} आवेदन हैं: {stages}।", "మీకు {n} దరఖాస్తులు ఉన్నాయి: {stages}.",
             "உங்களிடம் {n} விண்ணப்பங்கள் உள்ளன: {stages}.", "ನಿಮ್ಮ {n} ಅರ್ಜಿಗಳಿವೆ: {stages}.", "നിങ്ങൾക്ക് {n} അപേക്ഷകളുണ്ട്: {stages}."),
    "apps_none": ("You have no applications yet.", "अभी तक कोई आवेदन नहीं है।", "ఇంకా దరఖాస్తులు లేవు.", "இன்னும் விண்ணப்பங்கள் இல்லை.",
                  "ಇನ್ನೂ ಯಾವುದೇ ಅರ್ಜಿಗಳಿಲ್ಲ.", "ഇതുവരെ അപേക്ഷകളില്ല."),
    "iv": ("Your next interview is with {company} on {when}. You have {n} upcoming.",
           "आपका अगला इंटरव्यू {company} के साथ {when} को है। कुल {n} आने वाले हैं।",
           "మీ తదుపరి ఇంటర్వ్యూ {company}తో {when}న ఉంది. మొత్తం {n} రాబోతున్నాయి.",
           "உங்கள் அடுத்த நேர்காணல் {company} உடன் {when} அன்று. மொத்தம் {n} வரவுள்ளன.",
           "ನಿಮ್ಮ ಮುಂದಿನ ಸಂದರ್ಶನ {company} ಜೊತೆ {when} ರಂದು. ಒಟ್ಟು {n} ಬರಲಿವೆ.",
           "നിങ്ങളുടെ അടുത്ത ഇന്റർവ്യൂ {company} യുമായി {when} ന്. ആകെ {n} വരാനുണ്ട്."),
    "iv_none": ("No upcoming interviews yet.", "अभी कोई आने वाला इंटरव्यू नहीं है।", "ఇంకా రాబోయే ఇంటర్వ్యూలు లేవు.",
                "வரவிருக்கும் நேர்காணல்கள் இல்லை.", "ಮುಂಬರುವ ಸಂದರ್ಶನಗಳಿಲ್ಲ.", "വരാനിരിക്കുന്ന ഇന്റർവ്യൂകളില്ല."),
    "emails": ("You got {n} job emails today, {r} of them recruiter replies.",
               "आज आपको {n} जॉब ईमेल मिले, उनमें {r} रिक्रूटर के जवाब हैं।",
               "ఈ రోజు మీకు {n} ఉద్యోగ ఈమెయిల్స్ వచ్చాయి, వాటిలో {r} రిక్రూటర్ సమాధానాలు.",
               "இன்று உங்களுக்கு {n} வேலை மின்னஞ்சல்கள் வந்தன, அவற்றில் {r} பதில்கள்.",
               "ಇಂದು ನಿಮಗೆ {n} ಉದ್ಯೋಗ ಇಮೇಲ್‌ಗಳು ಬಂದಿವೆ, ಅವುಗಳಲ್ಲಿ {r} ಉತ್ತರಗಳು.",
               "ഇന്ന് നിങ്ങൾക്ക് {n} ജോലി ഇമെയിലുകൾ വന്നു, അതിൽ {r} മറുപടികൾ."),
    "fu": ("{n} follow-ups are due. Open Recruiters to send them.", "{n} फॉलो-अप बाकी हैं। भेजने के लिए रिक्रूटर खोलें।",
           "{n} ఫాలో-అప్‌లు పెండింగ్‌లో ఉన్నాయి. పంపడానికి రిక్రూటర్స్ తెరవండి.", "{n} ஃபாலோ-அப்கள் நிலுவையில் உள்ளன. அனுப்ப ஆட்சேர்ப்பாளர்கள் பக்கத்தைத் திறக்கவும்.",
           "{n} ಫಾಲೋ-ಅಪ್‌ಗಳು ಬಾಕಿ ಇವೆ. ಕಳುಹಿಸಲು ರಿಕ್ರೂಟರ್ಸ್ ತೆರೆಯಿರಿ.", "{n} ഫോളോ-അപ്പുകൾ ബാക്കിയുണ്ട്. അയയ്ക്കാൻ റിക്രൂട്ടേഴ്സ് തുറക്കുക."),
    "fu_none": ("No follow-ups are due right now.", "अभी कोई फॉलो-अप बाकी नहीं है।", "ఇప్పుడు ఫాలో-అప్‌లు ఏవీ లేవు.",
                "இப்போது ஃபாலோ-அப்கள் இல்லை.", "ಈಗ ಯಾವುದೇ ಫಾಲೋ-ಅಪ್ ಬಾಕಿ ಇಲ್ಲ.", "ഇപ്പോൾ ഫോളോ-അപ്പുകളൊന്നുമില്ല."),
    "profile": ("Your profile is {score} percent complete. Add: {missing}.", "आपकी प्रोफ़ाइल {score} प्रतिशत पूरी है। जोड़ें: {missing}।",
                "మీ ప్రొఫైల్ {score} శాతం పూర్తయింది. జోడించండి: {missing}.", "உங்கள் சுயவிவரம் {score} சதவீதம் முழுமை. சேர்க்கவும்: {missing}.",
                "ನಿಮ್ಮ ಪ್ರೊಫೈಲ್ {score} ಶೇಕಡಾ ಪೂರ್ಣವಾಗಿದೆ. ಸೇರಿಸಿ: {missing}.", "നിങ്ങളുടെ പ്രൊഫൈൽ {score} ശതമാനം പൂർത്തിയായി. ചേർക്കുക: {missing}."),
    "profile_full": ("Your profile is {score} percent complete. Run Resume health for line-by-line fixes.",
                     "आपकी प्रोफ़ाइल {score} प्रतिशत पूरी है। सुधार के लिए रिज़्यूमे हेल्थ चलाएँ।",
                     "మీ ప్రొఫైల్ {score} శాతం పూర్తయింది. సూచనల కోసం రెజ్యూమే హెల్త్ చూడండి.",
                     "உங்கள் சுயவிவரம் {score} சதவீதம் முழுமை. திருத்தங்களுக்கு ரெஸ்யூம் ஹெல்த் பார்க்கவும்.",
                     "ನಿಮ್ಮ ಪ್ರೊಫೈಲ್ {score} ಶೇಕಡಾ ಪೂರ್ಣವಾಗಿದೆ. ಸಲಹೆಗಳಿಗೆ ರೆಸ್ಯೂಮ್ ಹೆಲ್ತ್ ನೋಡಿ.",
                     "നിങ്ങളുടെ പ്രൊഫൈൽ {score} ശതമാനം പൂർത്തിയായി. തിരുത്തലുകൾക്ക് റെസ്യൂമെ ഹെൽത്ത് നോക്കുക."),
    "help": ("You can ask me: any new jobs, how are my applications, next interview, emails today, follow-ups due, or resume tips.",
             "आप पूछ सकते हैं: नई नौकरियाँ, आवेदन की स्थिति, अगला इंटरव्यू, आज के ईमेल, फॉलो-अप, या रिज़्यूमे टिप्स।",
             "మీరు అడగవచ్చు: కొత్త ఉద్యోగాలు, దరఖాస్తుల స్థితి, తదుపరి ఇంటర్వ్యూ, ఈ రోజు ఈమెయిల్స్, ఫాలో-అప్‌లు, రెజ్యూమే చిట్కాలు.",
             "நீங்கள் கேட்கலாம்: புதிய வேலைகள், விண்ணப்ப நிலை, அடுத்த நேர்காணல், இன்றைய மின்னஞ்சல்கள், ஃபாலோ-அப்கள், ரெஸ்யூம் குறிப்புகள்.",
             "ನೀವು ಕೇಳಬಹುದು: ಹೊಸ ಉದ್ಯೋಗಗಳು, ಅರ್ಜಿಗಳ ಸ್ಥಿತಿ, ಮುಂದಿನ ಸಂದರ್ಶನ, ಇಂದಿನ ಇಮೇಲ್‌ಗಳು, ಫಾಲೋ-ಅಪ್‌ಗಳು, ರೆಸ್ಯೂಮ್ ಸಲಹೆಗಳು.",
             "നിങ്ങൾക്ക് ചോദിക്കാം: പുതിയ ജോലികൾ, അപേക്ഷകളുടെ നില, അടുത്ത ഇന്റർവ്യൂ, ഇന്നത്തെ ഇമെയിലുകൾ, ഫോളോ-അപ്പുകൾ, റെസ്യൂമെ ടിപ്പുകൾ."),
}


def tr(key: str, lang: str, **kw) -> str:
    i = LANGS.index(lang) if lang in LANGS else 0
    return T[key][i].format(**kw)


def answer(intent: str, ctx: dict, lang: str) -> str:
    """Short, speakable answer in `lang` for a detected intent, from the user's own records only."""
    if intent == "jobs":
        jobs = ctx["top_jobs"]
        if not jobs:
            return tr("jobs_none", lang)
        top = "; ".join(tr("at", lang, title=j.get("title") or "?", company=j.get("company") or "?") for j in jobs[:3])
        return tr("jobs", lang, n=ctx.get("jobs_total", len(jobs)), top=top)
    if intent == "applications":
        apps = ctx["applications"]
        if not apps:
            return tr("apps_none", lang)
        stages = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in apps.items())
        return tr("apps", lang, n=sum(apps.values()), stages=stages)
    if intent == "interviews":
        ivs = ctx["upcoming_interviews"]
        if not ivs:
            return tr("iv_none", lang)
        return tr("iv", lang, company=ivs[0]["company"] or "?", when=ivs[0]["at"][:16].replace("T", " "), n=len(ivs))
    if intent == "emails":
        return tr("emails", lang, n=ctx.get("emails_today", 0), r=ctx.get("replies_today", 0))
    if intent == "followups":
        n = ctx.get("followups_due", 0)
        return tr("fu", lang, n=n) if n else tr("fu_none", lang)
    if intent == "profile":
        score, missing = ctx.get("completeness", 0), ctx.get("missing", [])
        return tr("profile", lang, score=score, missing=", ".join(missing[:3])) if missing else tr("profile_full", lang, score=score)
    return tr("help", lang)


def speakable(text: str) -> str:
    """Strips markdown and bullets so text-to-speech reads it naturally."""
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[*_`#>|]+", "", t)
    t = re.sub(r"^\s*([-•]|\d+\.)\s+", "", t, flags=re.M)
    t = re.sub(r"\s*\n+\s*", ". ", t.strip())
    t = re.sub(r"([.!?।])\.", r"\1", t)
    return re.sub(r"\s{2,}", " ", t).strip()
