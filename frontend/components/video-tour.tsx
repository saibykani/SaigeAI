"use client";

import { ChevronLeft, ChevronRight, Circle, Download, Pause, Play, Square, Volume2, VolumeX } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";

/**
 * Narrated video tour of Saige AI: screenshots with slow zoom, captions and spoken narration (the browser's own
 * text-to-speech) in English, Telugu, Hindi, Tamil, Kannada and Malayalam. "Record video" captures this tab with its
 * audio (Chrome: choose "This tab" + "Share tab audio") and downloads a .webm file you can share.
 */
export const LANGS = [
  { id: "en", label: "English", voice: "en-IN" },
  { id: "te", label: "తెలుగు", voice: "te-IN" },
  { id: "hi", label: "हिन्दी", voice: "hi-IN" },
  { id: "ta", label: "தமிழ்", voice: "ta-IN" },
  { id: "kn", label: "ಕನ್ನಡ", voice: "kn-IN" },
  { id: "ml", label: "മലയാളം", voice: "ml-IN" },
] as const;
type Lang = (typeof LANGS)[number]["id"];

export type Scene = { image: string; title: Record<Lang, string>; say: Record<Lang, string> };

export const SCENES: Scene[] = [
  { image: "/help/login.jpg",
    title: { en: "Welcome to Saige AI", te: "Saige AI కి స్వాగతం", hi: "Saige AI में आपका स्वागत है", ta: "Saige AI-க்கு வரவேற்கிறோம்", kn: "Saige AI ಗೆ ಸ್ವಾಗತ", ml: "Saige AI-ലേക്ക് സ്വാഗതം" },
    say: {
      en: "Welcome to Saige AI, your truthful career assistant. Sign up with your email or Google. Saige finds jobs, builds resumes and tracks applications, and never invents anything about you.",
      te: "Saige AI కి స్వాగతం. ఇది మీ నిజాయితీ గల కెరీర్ సహాయకుడు. మీ ఈమెయిల్ లేదా Google తో సైన్ అప్ చేయండి. Saige ఉద్యోగాలు వెతుకుతుంది, రెజ్యూమేలు తయారు చేస్తుంది, మీ గురించి ఏదీ కల్పించదు.",
      hi: "Saige AI में आपका स्वागत है, आपका सच्चा करियर सहायक। अपने ईमेल या Google से साइन अप करें। Saige नौकरियाँ ढूँढता है, रिज़्यूमे बनाता है और आपके बारे में कुछ भी मनगढ़ंत नहीं लिखता।",
      ta: "Saige AI-க்கு வரவேற்கிறோம், உங்கள் நேர்மையான தொழில் உதவியாளர். உங்கள் மின்னஞ்சல் அல்லது Google மூலம் பதிவு செய்யுங்கள். Saige வேலைகளைத் தேடுகிறது, ரெஸ்யூமே உருவாக்குகிறது, உங்களைப் பற்றி எதையும் கற்பனை செய்யாது.",
      kn: "Saige AI ಗೆ ಸ್ವಾಗತ, ನಿಮ್ಮ ಪ್ರಾಮಾಣಿಕ ವೃತ್ತಿ ಸಹಾಯಕ. ನಿಮ್ಮ ಇಮೇಲ್ ಅಥವಾ Google ಮೂಲಕ ಸೈನ್ ಅಪ್ ಮಾಡಿ. Saige ಉದ್ಯೋಗಗಳನ್ನು ಹುಡುಕುತ್ತದೆ, ರೆಸ್ಯೂಮ್ ತಯಾರಿಸುತ್ತದೆ ಮತ್ತು ನಿಮ್ಮ ಬಗ್ಗೆ ಏನನ್ನೂ ಕಲ್ಪಿಸುವುದಿಲ್ಲ.",
      ml: "Saige AI-ലേക്ക് സ്വാഗതം, നിങ്ങളുടെ സത്യസന്ധമായ കരിയർ സഹായി. ഇമെയിൽ അല്ലെങ്കിൽ Google ഉപയോഗിച്ച് സൈൻ അപ്പ് ചെയ്യുക. Saige ജോലികൾ കണ്ടെത്തുന്നു, റെസ്യൂമെ തയ്യാറാക്കുന്നു, നിങ്ങളെക്കുറിച്ച് ഒന്നും കെട്ടിച്ചമയ്ക്കുന്നില്ല.",
    } },
  { image: "/help/onboarding.jpg",
    title: { en: "Step 1: Upload your resume", te: "దశ 1: రెజ్యూమే అప్‌లోడ్", hi: "चरण 1: रिज़्यूमे अपलोड करें", ta: "படி 1: ரெஸ்யூமே பதிவேற்றம்", kn: "ಹಂತ 1: ರೆಸ್ಯೂಮ್ ಅಪ್‌ಲೋಡ್", ml: "ഘട്ടം 1: റെസ്യൂമെ അപ്‌ലോഡ്" },
    say: {
      en: "First, upload your resume as PDF or Word. Saige reads it and fills your profile: contact details, experience, skills, projects and education. Check the details, then choose the roles and cities you want.",
      te: "ముందుగా మీ రెజ్యూమేను PDF లేదా Word గా అప్‌లోడ్ చేయండి. Saige దాన్ని చదివి మీ ప్రొఫైల్ నింపుతుంది: కాంటాక్ట్, అనుభవం, నైపుణ్యాలు, ప్రాజెక్టులు, చదువు. వివరాలు సరిచూసి, మీకు కావలసిన ఉద్యోగాలు మరియు నగరాలు ఎంచుకోండి.",
      hi: "सबसे पहले अपना रिज़्यूमे PDF या Word में अपलोड करें। Saige उसे पढ़कर आपकी प्रोफ़ाइल भरता है: संपर्क, अनुभव, स्किल्स, प्रोजेक्ट और शिक्षा। विवरण जाँचें, फिर अपनी पसंद की भूमिकाएँ और शहर चुनें।",
      ta: "முதலில் உங்கள் ரெஸ்யூமேவை PDF அல்லது Word ஆக பதிவேற்றுங்கள். Saige அதைப் படித்து உங்கள் சுயவிவரத்தை நிரப்புகிறது: தொடர்பு, அனுபவம், திறன்கள், திட்டங்கள், கல்வி. விவரங்களைச் சரிபார்த்து, விரும்பும் பணிகள் மற்றும் நகரங்களைத் தேர்ந்தெடுங்கள்.",
      kn: "ಮೊದಲು ನಿಮ್ಮ ರೆಸ್ಯೂಮ್ ಅನ್ನು PDF ಅಥವಾ Word ಆಗಿ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ. Saige ಅದನ್ನು ಓದಿ ನಿಮ್ಮ ಪ್ರೊಫೈಲ್ ತುಂಬುತ್ತದೆ: ಸಂಪರ್ಕ, ಅನುಭವ, ಕೌಶಲ್ಯ, ಯೋಜನೆಗಳು, ಶಿಕ್ಷಣ. ವಿವರ ಪರಿಶೀಲಿಸಿ, ನಿಮಗೆ ಬೇಕಾದ ಹುದ್ದೆಗಳು ಮತ್ತು ನಗರಗಳನ್ನು ಆರಿಸಿ.",
      ml: "ആദ്യം നിങ്ങളുടെ റെസ്യൂമെ PDF അല്ലെങ്കിൽ Word ആയി അപ്‌ലോഡ് ചെയ്യുക. Saige അത് വായിച്ച് പ്രൊഫൈൽ പൂരിപ്പിക്കുന്നു: ബന്ധപ്പെടാനുള്ള വിവരം, അനുഭവം, കഴിവുകൾ, പ്രോജക്റ്റുകൾ, വിദ്യാഭ്യാസം. വിവരങ്ങൾ പരിശോധിച്ച്, ആഗ്രഹിക്കുന്ന ജോലികളും നഗരങ്ങളും തിരഞ്ഞെടുക്കുക.",
    } },
  { image: "/help/dashboard.jpg",
    title: { en: "Your dashboard", te: "మీ డాష్‌బోర్డ్", hi: "आपका डैशबोर्ड", ta: "உங்கள் டாஷ்போர்டு", kn: "ನಿಮ್ಮ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್", ml: "നിങ്ങളുടെ ഡാഷ്‌ബോർഡ്" },
    say: {
      en: "The dashboard shows today's numbers: new jobs, strong matches, applications and replies. The coach card lists the top fixes for your resume and profile.",
      te: "డాష్‌బోర్డ్ ఈరోజు సంఖ్యలు చూపిస్తుంది: కొత్త ఉద్యోగాలు, బలమైన మ్యాచ్‌లు, దరఖాస్తులు మరియు స్పందనలు. కోచ్ కార్డ్ మీ రెజ్యూమే కోసం ముఖ్యమైన మార్పులు చూపిస్తుంది.",
      hi: "डैशबोर्ड आज के आँकड़े दिखाता है: नई नौकरियाँ, अच्छे मैच, आवेदन और जवाब। कोच कार्ड आपके रिज़्यूमे और प्रोफ़ाइल के सबसे ज़रूरी सुधार बताता है।",
      ta: "டாஷ்போர்டு இன்றைய எண்களைக் காட்டுகிறது: புதிய வேலைகள், வலுவான பொருத்தங்கள், விண்ணப்பங்கள், பதில்கள். கோச் அட்டை உங்கள் ரெஸ்யூமேக்கான முக்கிய திருத்தங்களைக் காட்டுகிறது.",
      kn: "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್ ಇಂದಿನ ಸಂಖ್ಯೆಗಳನ್ನು ತೋರಿಸುತ್ತದೆ: ಹೊಸ ಉದ್ಯೋಗಗಳು, ಉತ್ತಮ ಹೊಂದಾಣಿಕೆಗಳು, ಅರ್ಜಿಗಳು ಮತ್ತು ಉತ್ತರಗಳು. ಕೋಚ್ ಕಾರ್ಡ್ ನಿಮ್ಮ ರೆಸ್ಯೂಮ್‌ಗೆ ಮುಖ್ಯ ಸುಧಾರಣೆಗಳನ್ನು ಹೇಳುತ್ತದೆ.",
      ml: "ഡാഷ്‌ബോർഡ് ഇന്നത്തെ കണക്കുകൾ കാണിക്കുന്നു: പുതിയ ജോലികൾ, മികച്ച പൊരുത്തങ്ങൾ, അപേക്ഷകൾ, മറുപടികൾ. കോച്ച് കാർഡ് നിങ്ങളുടെ റെസ്യൂമെയ്ക്കുള്ള പ്രധാന തിരുത്തലുകൾ കാണിക്കുന്നു.",
    } },
  { image: "/help/jobs.jpg",
    title: { en: "Find jobs", te: "ఉద్యోగాలు వెతకండి", hi: "नौकरियाँ खोजें", ta: "வேலைகளைத் தேடுங்கள்", kn: "ಉದ್ಯೋಗ ಹುಡುಕಿ", ml: "ജോലികൾ കണ്ടെത്തുക" },
    say: {
      en: "Jobs for you lists fresh openings ranked by match percentage. Career portals scans more than sixty five company career sites. Open any job to see which skills you have and which are missing.",
      te: "Jobs for you లో కొత్త ఉద్యోగాలు మ్యాచ్ శాతం ప్రకారం కనిపిస్తాయి. Career portals అరవై ఐదు కంటే ఎక్కువ కంపెనీ కెరీర్ సైట్‌లను స్కాన్ చేస్తుంది. ఏ ఉద్యోగం తెరిచినా మీకు ఉన్న మరియు లేని నైపుణ్యాలు కనిపిస్తాయి.",
      hi: "Jobs for you में नई नौकरियाँ मैच प्रतिशत के अनुसार दिखती हैं। Career portals पैंसठ से ज़्यादा कंपनियों की करियर साइट स्कैन करता है। कोई भी नौकरी खोलें और देखें कौन सी स्किल्स आपके पास हैं और कौन सी नहीं।",
      ta: "Jobs for you புதிய வேலைகளைப் பொருத்த சதவீதப்படி காட்டுகிறது. Career portals அறுபத்தைந்துக்கும் மேற்பட்ட நிறுவன தளங்களைச் சோதிக்கிறது. எந்த வேலையைத் திறந்தாலும் உங்களிடம் உள்ள மற்றும் இல்லாத திறன்கள் தெரியும்.",
      kn: "Jobs for you ಹೊಸ ಉದ್ಯೋಗಗಳನ್ನು ಹೊಂದಾಣಿಕೆ ಶೇಕಡಾವಾರು ಪ್ರಕಾರ ತೋರಿಸುತ್ತದೆ. Career portals ಅರವತ್ತೈದಕ್ಕೂ ಹೆಚ್ಚು ಕಂಪನಿ ವೆಬ್‌ಸೈಟ್‌ಗಳನ್ನು ಸ್ಕ್ಯಾನ್ ಮಾಡುತ್ತದೆ. ಯಾವುದೇ ಉದ್ಯೋಗ ತೆರೆದರೆ ನಿಮ್ಮಲ್ಲಿರುವ ಮತ್ತು ಇಲ್ಲದ ಕೌಶಲ್ಯಗಳು ಕಾಣುತ್ತವೆ.",
      ml: "Jobs for you പുതിയ ജോലികൾ പൊരുത്ത ശതമാനം അനുസരിച്ച് കാണിക്കുന്നു. Career portals അറുപത്തഞ്ചിലധികം കമ്പനി സൈറ്റുകൾ സ്കാൻ ചെയ്യുന്നു. ഏത് ജോലി തുറന്നാലും നിങ്ങൾക്കുള്ളതും ഇല്ലാത്തതുമായ കഴിവുകൾ കാണാം.",
    } },
  { image: "/help/ats-coach.jpg",
    title: { en: "100% ATS resume", te: "100% ATS రెజ్యూమే", hi: "100% ATS रिज़्यूमे", ta: "100% ATS ரெஸ்யூமே", kn: "100% ATS ರೆಸ್ಯೂಮ್", ml: "100% ATS റെസ്യൂമെ" },
    say: {
      en: "In Resume and ATS, type any role. The ATS coach shows your weak spots and builds a fitted resume using only facts from your profile. Download it as PDF or Word.",
      te: "Resume & ATS లో ఏ ఉద్యోగ పేరైనా టైప్ చేయండి. ATS కోచ్ బలహీనతలు చూపి, మీ ప్రొఫైల్‌లోని నిజాలతో మాత్రమే సరిపోయే రెజ్యూమే తయారు చేస్తుంది. PDF లేదా Word గా డౌన్‌లోడ్ చేయండి.",
      hi: "Resume & ATS में कोई भी भूमिका लिखें। ATS कोच कमज़ोरियाँ दिखाता है और सिर्फ़ आपकी प्रोफ़ाइल के तथ्यों से सही रिज़्यूमे बनाता है। इसे PDF या Word में डाउनलोड करें।",
      ta: "Resume & ATS-இல் எந்தப் பணியையும் தட்டச்சு செய்யுங்கள். ATS கோச் பலவீனங்களைக் காட்டி, உங்கள் சுயவிவர உண்மைகளை மட்டும் கொண்டு ரெஸ்யூமே உருவாக்குகிறது. PDF அல்லது Word ஆகப் பதிவிறக்குங்கள்.",
      kn: "Resume & ATS ನಲ್ಲಿ ಯಾವುದೇ ಹುದ್ದೆ ಟೈಪ್ ಮಾಡಿ. ATS ಕೋಚ್ ದುರ್ಬಲ ಅಂಶಗಳನ್ನು ತೋರಿಸಿ, ನಿಮ್ಮ ಪ್ರೊಫೈಲ್‌ನ ಸತ್ಯಗಳಿಂದಲೇ ರೆಸ್ಯೂಮ್ ತಯಾರಿಸುತ್ತದೆ. PDF ಅಥವಾ Word ಆಗಿ ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ.",
      ml: "Resume & ATS-ൽ ഏത് ജോലിയും ടൈപ്പ് ചെയ്യുക. ATS കോച്ച് ദുർബലതകൾ കാണിച്ച്, പ്രൊഫൈലിലെ വസ്തുതകൾ മാത്രം ഉപയോഗിച്ച് റെസ്യൂമെ തയ്യാറാക്കുന്നു. PDF അല്ലെങ്കിൽ Word ആയി ഡൗൺലോഡ് ചെയ്യുക.",
    } },
  { image: "/help/health.jpg",
    title: { en: "Resume health", te: "రెజ్యూమే హెల్త్", hi: "रिज़्यूमे हेल्थ", ta: "ரெஸ்யூமே ஹெல்த்", kn: "ರೆಸ್ಯೂಮ್ ಹೆಲ್ತ್", ml: "റെസ്യൂമെ ഹെൽത്ത്" },
    say: {
      en: "Resume health compares every line side by side: your line and the better version. Add real numbers where asked, press Apply all, and a new version is saved.",
      te: "రెజ్యూమే హెల్త్ ప్రతి లైన్‌ను పక్కపక్కనే చూపిస్తుంది: మీ లైన్ మరియు మెరుగైన రూపం. అడిగిన చోట నిజమైన సంఖ్యలు జోడించి Apply all నొక్కండి, కొత్త వెర్షన్ సేవ్ అవుతుంది.",
      hi: "रिज़्यूमे हेल्थ हर लाइन को आमने-सामने दिखाता है: आपकी लाइन और बेहतर रूप। जहाँ पूछा जाए वहाँ असली आँकड़े जोड़ें, Apply all दबाएँ, और नया वर्ज़न सेव हो जाता है।",
      ta: "ரெஸ்யூமே ஹெல்த் ஒவ்வொரு வரியையும் பக்கம் பக்கமாகக் காட்டுகிறது: உங்கள் வரியும் சிறந்த வடிவமும். கேட்கும் இடத்தில் உண்மையான எண்களைச் சேர்த்து Apply all அழுத்துங்கள், புதிய பதிப்பு சேமிக்கப்படும்.",
      kn: "ರೆಸ್ಯೂಮ್ ಹೆಲ್ತ್ ಪ್ರತಿ ಸಾಲನ್ನು ಅಕ್ಕಪಕ್ಕ ತೋರಿಸುತ್ತದೆ: ನಿಮ್ಮ ಸಾಲು ಮತ್ತು ಉತ್ತಮ ರೂಪ. ಕೇಳಿದಲ್ಲಿ ನಿಜವಾದ ಸಂಖ್ಯೆಗಳನ್ನು ಸೇರಿಸಿ Apply all ಒತ್ತಿ, ಹೊಸ ಆವೃತ್ತಿ ಉಳಿಯುತ್ತದೆ.",
      ml: "റെസ്യൂമെ ഹെൽത്ത് ഓരോ വരിയും അടുത്തടുത്ത് കാണിക്കുന്നു: നിങ്ങളുടെ വരിയും മെച്ചപ്പെട്ട രൂപവും. ചോദിക്കുന്നിടത്ത് യഥാർത്ഥ സംഖ്യകൾ ചേർത്ത് Apply all അമർത്തുക, പുതിയ പതിപ്പ് സേവ് ആകും.",
    } },
  { image: "/help/applications.jpg",
    title: { en: "Apply with approval", te: "అనుమతితో దరఖాస్తు", hi: "मंज़ूरी के साथ आवेदन", ta: "ஒப்புதலுடன் விண்ணப்பம்", kn: "ಅನುಮೋದನೆಯೊಂದಿಗೆ ಅರ್ಜಿ", ml: "അനുമതിയോടെ അപേക്ഷ" },
    say: {
      en: "Saige prepares the resume, cover letter and answers. Nothing is sent until you approve it in Applications. Track every reply and interview in one place.",
      te: "Saige రెజ్యూమే, కవర్ లెటర్ మరియు సమాధానాలు సిద్ధం చేస్తుంది. Applications లో మీరు అనుమతించే వరకు ఏదీ పంపబడదు. ప్రతి స్పందన మరియు ఇంటర్వ్యూ ఒకే చోట చూడండి.",
      hi: "Saige रिज़्यूमे, कवर लेटर और जवाब तैयार करता है। जब तक आप Applications में मंज़ूरी न दें, कुछ भी नहीं भेजा जाता। हर जवाब और इंटरव्यू एक ही जगह देखें।",
      ta: "Saige ரெஸ்யூமே, கவர் லெட்டர், பதில்களைத் தயாரிக்கிறது. Applications-இல் நீங்கள் ஒப்புதல் தரும் வரை எதுவும் அனுப்பப்படாது. ஒவ்வொரு பதிலையும் நேர்காணலையும் ஒரே இடத்தில் பாருங்கள்.",
      kn: "Saige ರೆಸ್ಯೂಮ್, ಕವರ್ ಲೆಟರ್ ಮತ್ತು ಉತ್ತರಗಳನ್ನು ಸಿದ್ಧಪಡಿಸುತ್ತದೆ. Applications ನಲ್ಲಿ ನೀವು ಅನುಮೋದಿಸುವವರೆಗೆ ಏನನ್ನೂ ಕಳುಹಿಸುವುದಿಲ್ಲ. ಎಲ್ಲಾ ಉತ್ತರಗಳು ಮತ್ತು ಸಂದರ್ಶನಗಳನ್ನು ಒಂದೇ ಕಡೆ ನೋಡಿ.",
      ml: "Saige റെസ്യൂമെ, കവർ ലെറ്റർ, ഉത്തരങ്ങൾ എന്നിവ തയ്യാറാക്കുന്നു. Applications-ൽ നിങ്ങൾ അനുമതി നൽകുന്നത് വരെ ഒന്നും അയയ്ക്കില്ല. എല്ലാ മറുപടികളും ഇന്റർവ്യൂകളും ഒരിടത്ത് കാണുക.",
    } },
  { image: "/help/integrations.jpg",
    title: { en: "Connect Gmail & alerts", te: "Gmail & అలర్ట్‌లు", hi: "Gmail और अलर्ट जोड़ें", ta: "Gmail & அறிவிப்புகள்", kn: "Gmail & ಎಚ್ಚರಿಕೆಗಳು", ml: "Gmail & അലേർട്ടുകൾ" },
    say: {
      en: "In Integrations, connect Gmail so Saige can track recruiter replies, and add Telegram or WhatsApp for instant alerts. Install the Chrome extension to save and fill jobs from any site.",
      te: "Integrations లో Gmail కనెక్ట్ చేయండి, అప్పుడు Saige రిక్రూటర్ స్పందనలను ట్రాక్ చేస్తుంది. వెంటనే అలర్ట్‌ల కోసం Telegram లేదా WhatsApp జోడించండి. ఏ సైట్ నుండైనా ఉద్యోగాలు సేవ్ చేయడానికి Chrome ఎక్స్‌టెన్షన్ ఇన్‌స్టాల్ చేయండి.",
      hi: "Integrations में Gmail जोड़ें ताकि Saige रिक्रूटर के जवाब ट्रैक कर सके, और तुरंत अलर्ट के लिए Telegram या WhatsApp जोड़ें। किसी भी साइट से नौकरी सेव करने के लिए Chrome एक्सटेंशन इंस्टॉल करें।",
      ta: "Integrations-இல் Gmail-ஐ இணைத்தால் Saige ரெக்ரூட்டர் பதில்களைக் கண்காணிக்கும். உடனடி அறிவிப்புகளுக்கு Telegram அல்லது WhatsApp சேர்க்கவும். எந்தத் தளத்திலிருந்தும் வேலைகளைச் சேமிக்க Chrome நீட்டிப்பை நிறுவுங்கள்.",
      kn: "Integrations ನಲ್ಲಿ Gmail ಸಂಪರ್ಕಿಸಿ, Saige ರಿಕ್ರೂಟರ್ ಉತ್ತರಗಳನ್ನು ಗಮನಿಸುತ್ತದೆ. ತಕ್ಷಣದ ಎಚ್ಚರಿಕೆಗಳಿಗೆ Telegram ಅಥವಾ WhatsApp ಸೇರಿಸಿ. ಯಾವುದೇ ಸೈಟ್‌ನಿಂದ ಉದ್ಯೋಗ ಉಳಿಸಲು Chrome ಎಕ್ಸ್‌ಟೆನ್ಶನ್ ಇನ್‌ಸ್ಟಾಲ್ ಮಾಡಿ.",
      ml: "Integrations-ൽ Gmail ബന്ധിപ്പിച്ചാൽ Saige റിക്രൂട്ടർ മറുപടികൾ ട്രാക്ക് ചെയ്യും. ഉടനടി അലേർട്ടുകൾക്ക് Telegram അല്ലെങ്കിൽ WhatsApp ചേർക്കുക. ഏത് സൈറ്റിൽ നിന്നും ജോലി സേവ് ചെയ്യാൻ Chrome എക്സ്റ്റൻഷൻ ഇൻസ്റ്റാൾ ചെയ്യുക.",
    } },
  { image: "/help/recruiters.jpg",
    title: { en: "Recruiters & referrals", te: "రిక్రూటర్లు & రిఫరల్స్", hi: "रिक्रूटर और रेफ़रल", ta: "ரெக்ரூட்டர்கள் & பரிந்துரைகள்", kn: "ರಿಕ್ರೂಟರ್‌ಗಳು & ರೆಫರಲ್", ml: "റിക്രൂട്ടർമാർ & റെഫറൽ" },
    say: {
      en: "Network helps you reach recruiters with truthful, personal messages, at most ten a day. Saige reminds you to follow up when a company goes silent.",
      te: "Network ద్వారా నిజాయితీ గల వ్యక్తిగత సందేశాలతో రిక్రూటర్లను సంప్రదించండి, రోజుకు గరిష్టంగా పది. కంపెనీ స్పందించకపోతే ఫాలో అప్ చేయమని Saige గుర్తు చేస్తుంది.",
      hi: "Network से रिक्रूटर्स को सच्चे, निजी संदेश भेजें, दिन में अधिकतम दस। कंपनी चुप हो जाए तो Saige आपको फ़ॉलो-अप की याद दिलाता है।",
      ta: "Network மூலம் நேர்மையான தனிப்பட்ட செய்திகளுடன் ரெக்ரூட்டர்களை அணுகுங்கள், நாளொன்றுக்கு அதிகபட்சம் பத்து. நிறுவனம் பதில் தராவிட்டால் Saige நினைவூட்டும்.",
      kn: "Network ಮೂಲಕ ಪ್ರಾಮಾಣಿಕ ವೈಯಕ್ತಿಕ ಸಂದೇಶಗಳೊಂದಿಗೆ ರಿಕ್ರೂಟರ್‌ಗಳನ್ನು ಸಂಪರ್ಕಿಸಿ, ದಿನಕ್ಕೆ ಗರಿಷ್ಠ ಹತ್ತು. ಕಂಪನಿ ಉತ್ತರಿಸದಿದ್ದರೆ Saige ನೆನಪಿಸುತ್ತದೆ.",
      ml: "Network വഴി സത്യസന്ധമായ വ്യക്തിഗത സന്ദേശങ്ങളോടെ റിക്രൂട്ടർമാരെ സമീപിക്കുക, ദിവസം പരമാവധി പത്ത്. കമ്പനി മറുപടി നൽകിയില്ലെങ്കിൽ Saige ഓർമ്മിപ്പിക്കും.",
    } },
  { image: "/help/portfolio.jpg",
    title: { en: "Your portfolio website", te: "మీ పోర్ట్‌ఫోలియో వెబ్‌సైట్", hi: "आपकी पोर्टफ़ोलियो वेबसाइट", ta: "உங்கள் போர்ட்ஃபோலியோ இணையதளம்", kn: "ನಿಮ್ಮ ಪೋರ್ಟ್‌ಫೋಲಿಯೊ ವೆಬ್‌ಸೈಟ್", ml: "നിങ്ങളുടെ പോർട്ട്‌ഫോളിയോ വെബ്‌സൈറ്റ്" },
    say: {
      en: "Portfolio turns your profile into a live, animated website. Pick a template, preview it with your own data and publish it to a link you can share with recruiters.",
      te: "Portfolio మీ ప్రొఫైల్‌ను యానిమేటెడ్ వెబ్‌సైట్‌గా మారుస్తుంది. టెంప్లేట్ ఎంచుకుని, మీ వివరాలతో చూసి, రిక్రూటర్లకు పంపగల లింక్‌గా పబ్లిష్ చేయండి.",
      hi: "Portfolio आपकी प्रोफ़ाइल को एक लाइव, एनिमेटेड वेबसाइट बना देता है। टेम्पलेट चुनें, अपने डेटा के साथ देखें और रिक्रूटर्स के साथ शेयर करने के लिए लिंक पर पब्लिश करें।",
      ta: "Portfolio உங்கள் சுயவிவரத்தை அனிமேஷன் இணையதளமாக மாற்றுகிறது. டெம்ப்ளேட்டைத் தேர்ந்தெடுத்து, உங்கள் தரவுடன் பார்த்து, ரெக்ரூட்டர்களுடன் பகிரக்கூடிய இணைப்பாக வெளியிடுங்கள்.",
      kn: "Portfolio ನಿಮ್ಮ ಪ್ರೊಫೈಲ್ ಅನ್ನು ಅನಿಮೇಟೆಡ್ ವೆಬ್‌ಸೈಟ್ ಆಗಿ ಮಾಡುತ್ತದೆ. ಟೆಂಪ್ಲೇಟ್ ಆರಿಸಿ, ನಿಮ್ಮ ಮಾಹಿತಿಯೊಂದಿಗೆ ನೋಡಿ, ರಿಕ್ರೂಟರ್‌ಗಳಿಗೆ ಹಂಚಬಹುದಾದ ಲಿಂಕ್ ಆಗಿ ಪ್ರಕಟಿಸಿ.",
      ml: "Portfolio നിങ്ങളുടെ പ്രൊഫൈലിനെ ആനിമേറ്റഡ് വെബ്‌സൈറ്റാക്കി മാറ്റുന്നു. ടെംപ്ലേറ്റ് തിരഞ്ഞെടുത്ത്, നിങ്ങളുടെ വിവരങ്ങളോടെ കണ്ട്, റിക്രൂട്ടർമാരുമായി പങ്കിടാവുന്ന ലിങ്കായി പ്രസിദ്ധീകരിക്കുക.",
    } },
  { image: "/help/assistant.jpg",
    title: { en: "Ask Saige anything", te: "Saige ని ఏదైనా అడగండి", hi: "Saige से कुछ भी पूछें", ta: "Saige-இடம் எதையும் கேளுங்கள்", kn: "Saige ಗೆ ಏನಾದರೂ ಕೇಳಿ", ml: "Saige-നോട് എന്തും ചോദിക്കൂ" },
    say: {
      en: "The Saige assistant answers questions about your jobs, applications and next steps. Your data stays private to your account. Good luck with your search!",
      te: "Saige అసిస్టెంట్ మీ ఉద్యోగాలు, దరఖాస్తులు మరియు తదుపరి దశల గురించి సమాధానాలు ఇస్తుంది. మీ డేటా మీ ఖాతాకే పరిమితం. మీ ఉద్యోగ వేటకు శుభాకాంక్షలు!",
      hi: "Saige असिस्टेंट आपकी नौकरियों, आवेदनों और अगले कदमों के सवालों का जवाब देता है। आपका डेटा सिर्फ़ आपके खाते तक सीमित रहता है। आपकी खोज के लिए शुभकामनाएँ!",
      ta: "Saige உதவியாளர் உங்கள் வேலைகள், விண்ணப்பங்கள், அடுத்த படிகள் பற்றிய கேள்விகளுக்குப் பதில் தருகிறது. உங்கள் தரவு உங்கள் கணக்கில் மட்டுமே. உங்கள் தேடலுக்கு வாழ்த்துகள்!",
      kn: "Saige ಸಹಾಯಕ ನಿಮ್ಮ ಉದ್ಯೋಗ, ಅರ್ಜಿ ಮತ್ತು ಮುಂದಿನ ಹಂತಗಳ ಪ್ರಶ್ನೆಗಳಿಗೆ ಉತ್ತರಿಸುತ್ತದೆ. ನಿಮ್ಮ ಡೇಟಾ ನಿಮ್ಮ ಖಾತೆಗೆ ಮಾತ್ರ ಸೀಮಿತ. ನಿಮ್ಮ ಹುಡುಕಾಟಕ್ಕೆ ಶುಭವಾಗಲಿ!",
      ml: "Saige അസിസ്റ്റന്റ് നിങ്ങളുടെ ജോലികൾ, അപേക്ഷകൾ, അടുത്ത ഘട്ടങ്ങൾ എന്നിവയെക്കുറിച്ചുള്ള ചോദ്യങ്ങൾക്ക് ഉത്തരം നൽകുന്നു. നിങ്ങളുടെ ഡാറ്റ നിങ്ങളുടെ അക്കൗണ്ടിൽ മാത്രം. നിങ്ങളുടെ തിരയലിന് ആശംസകൾ!",
    } },
];

const SILENT_MS = 7000;

/** Voices for a language, best first: neural "Natural"/"Online" voices (Edge), then Google voices (Chrome), then the rest. */
export function voicesFor(code: string): SpeechSynthesisVoice[] {
  if (typeof speechSynthesis === "undefined") return [];
  const base = code.split("-")[0];
  const rank = (v: SpeechSynthesisVoice) => (/natural|neural/i.test(v.name) ? 0 : /online/i.test(v.name) ? 1 : /google/i.test(v.name) ? 2 : 3) + (v.lang.replace("_", "-") === code ? 0 : 0.5);
  return speechSynthesis.getVoices().filter((v) => v.lang.replace("_", "-").toLowerCase().startsWith(base)).sort((a, b) => rank(a) - rank(b));
}

function pickVoice(code: string, name?: string): SpeechSynthesisVoice | null {
  const vs = voicesFor(code);
  return vs.find((v) => v.name === name) ?? vs[0] ?? null;
}

/** Talking AI presenter: blinks, breathes and moves its mouth on every spoken word. */
function Presenter({ talking, pulse }: { talking: boolean; pulse: number }) {
  return (
    <div className={cn("presenter", talking && "talking")} aria-hidden>
      <svg viewBox="0 0 120 120" className="size-full">
        <defs>
          <radialGradient id="pf" cx="50%" cy="38%" r="65%"><stop offset="0" stopColor="#3a3a44" /><stop offset="1" stopColor="#141418" /></radialGradient>
        </defs>
        <circle cx="60" cy="60" r="58" fill="url(#pf)" stroke="var(--primary)" strokeWidth="2.5" />
        <circle cx="60" cy="60" r="52" fill="none" stroke="var(--primary)" strokeOpacity=".25" strokeDasharray="3 6" className="pr-ring" />
        <g className="pr-eyes">
          <ellipse cx="44" cy="52" rx="7" ry="8" fill="#fff" /><ellipse cx="76" cy="52" rx="7" ry="8" fill="#fff" />
          <circle cx="45" cy="53" r="3.6" fill="var(--primary)" /><circle cx="77" cy="53" r="3.6" fill="var(--primary)" />
        </g>
        <ellipse key={pulse} cx="60" cy="80" rx="13" ry={talking ? 7 : 2.5} fill="var(--primary)" className={talking ? "pr-mouth" : ""} />
      </svg>
    </div>
  );
}

type Props = { scenes?: Scene[]; englishOnly?: boolean; start?: number; autoPlay?: boolean; audioFor?: (i: number, lang: Lang) => string | null };
const quickAudio = (i: number, lang: Lang) => `/help/audio/q${i}-${lang}.mp3`;

export function VideoTour({ scenes = SCENES, englishOnly = false, start = 0, autoPlay = false, audioFor = quickAudio }: Props) {
  const SCENES_ = scenes;
  const [lang, setLang] = useState<Lang>("en");
  const [i, setI] = useState(start);
  const [playing, setPlaying] = useState(autoPlay);
  const [voiceName, setVoiceName] = useState("");
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [talking, setTalking] = useState(false);
  const [pulse, setPulse] = useState(0);
  useEffect(() => { setI(start); }, [start, scenes]);
  const [muted, setMuted] = useState(false);
  const [hasVoice, setHasVoice] = useState(true);
  const [rec, setRec] = useState<MediaRecorder | null>(null);
  const [recErr, setRecErr] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scene = SCENES_[i];
  const L = LANGS.find((l) => l.id === lang)!;

  const audio = useRef<HTMLAudioElement | null>(null);
  const stopAudio = () => {
    if (timer.current) clearTimeout(timer.current);
    if (audio.current) { audio.current.onended = null; audio.current.onerror = null; audio.current.pause(); audio.current = null; }
    if (typeof speechSynthesis !== "undefined") speechSynthesis.cancel();
  };

  const advance = useCallback(() => {
    setI((n) => {
      if (n + 1 >= SCENES_.length) { setPlaying(false); return n; }
      return n + 1;
    });
  }, []);

  useEffect(() => {
    const check = () => { const vs = voicesFor(L.voice); setVoices(vs); setHasVoice(vs.length > 0); };
    check();
    if (typeof speechSynthesis !== "undefined") speechSynthesis.addEventListener("voiceschanged", check);
    return () => { if (typeof speechSynthesis !== "undefined") speechSynthesis.removeEventListener("voiceschanged", check); };
  }, [L.voice]);

  useEffect(() => {
    stopAudio();
    if (!playing) return;
    const text = scene.say[lang];
    const speakDevice = () => {
      const voice = pickVoice(L.voice, voiceName);
      if (!voice || typeof SpeechSynthesisUtterance === "undefined") { timer.current = setTimeout(advance, Math.max(SILENT_MS, text.length * 55)); return; }
      const u = new SpeechSynthesisUtterance(text);
      u.voice = voice;
      u.lang = voice.lang;
      u.onstart = () => setTalking(true);
      u.onboundary = () => setPulse((n) => n + 1);
      u.onend = () => { setTalking(false); timer.current = setTimeout(advance, 700); };
      speechSynthesis.speak(u);
    };
    const src = audioFor(i, lang);
    if (!muted && src && !voiceName) {  // studio neural voice (pre-recorded MP3), works on every device
      const a = new Audio(src);
      audio.current = a;
      let tick: ReturnType<typeof setInterval> | undefined;
      a.onplay = () => { setTalking(true); tick = setInterval(() => setPulse((n) => n + 1), 260); };
      a.onended = () => { clearInterval(tick); setTalking(false); timer.current = setTimeout(advance, 700); };
      a.onpause = () => { clearInterval(tick); setTalking(false); };
      a.onerror = () => { clearInterval(tick); audio.current = null; speakDevice(); };
      a.play().catch(() => { clearInterval(tick); setPlaying(false); });
      return stopAudio;
    }
    const voice = pickVoice(L.voice, voiceName);
    if (!muted && voice && typeof SpeechSynthesisUtterance !== "undefined") {
      const u = new SpeechSynthesisUtterance(text);
      u.voice = voice;
      u.lang = voice.lang;
      u.rate = /natural|neural|online/i.test(voice.name) ? 1 : 0.92;
      u.onstart = () => setTalking(true);
      u.onboundary = () => setPulse((n) => n + 1);
      u.onend = () => { setTalking(false); timer.current = setTimeout(advance, 700); };
      speechSynthesis.speak(u);
    } else {
      timer.current = setTimeout(advance, Math.max(SILENT_MS, text.length * 55));
    }
    return stopAudio;
  }, [playing, i, lang, muted, scene, L.voice, voiceName, advance, audioFor]);
  useEffect(() => { if (!playing) setTalking(false); }, [playing]);

  useEffect(() => () => stopAudio(), []);

  async function record() {
    setRecErr(null);
    try {
      const md = navigator.mediaDevices as MediaDevices & { getDisplayMedia(o: object): Promise<MediaStream> };
      const stream = await md.getDisplayMedia({ video: { frameRate: 30 }, audio: true, preferCurrentTab: true, selfBrowserSurface: "include" });
      const chunks: Blob[] = [];
      const mr = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus") ? "video/webm;codecs=vp9,opus" : "video/webm" });
      mr.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob(chunks, { type: "video/webm" }));
        a.download = `Saige-AI-tour-${L.id}.webm`;
        a.click();
        setRec(null);
      };
      stream.getVideoTracks()[0].addEventListener("ended", () => { if (mr.state !== "inactive") mr.stop(); });
      mr.start(1000);
      setRec(mr);
      setI(0);
      setPlaying(true);
    } catch {
      setRecErr("Recording was cancelled or isn't supported in this browser. Use Chrome or Edge, choose “This tab” and turn on “Share tab audio”.");
    }
  }

  useEffect(() => {
    if (rec && !playing && i === SCENES_.length - 1) setTimeout(() => { if (rec.state !== "inactive") rec.stop(); }, 1500);
  }, [rec, playing, i]);

  return (
    <div className="overflow-hidden rounded-3xl border bg-black text-white">
      <div className="relative aspect-video overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element -- static screenshots */}
        <img key={`${i}-${playing}`} src={scene.image} alt={scene.title.en} className={cn("absolute inset-0 h-full w-full object-cover object-left-top", playing && "tour-kb")} />
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent" />
        <div className="absolute left-5 top-4 flex items-center gap-2 rounded-full bg-black/60 px-3 py-1 text-xs">
          <span className="font-semibold">Saige AI</span><span className="opacity-60">· {i + 1}/{SCENES_.length}</span>
          {rec && <span className="flex items-center gap-1 text-red-400"><Circle className="size-3 fill-current" /> REC</span>}
        </div>
        <div className="absolute bottom-24 right-4 size-20 md:bottom-auto md:right-6 md:top-6 md:size-28"><Presenter talking={talking || (playing && (muted || !hasVoice))} pulse={pulse} /></div>
        <div className="absolute inset-x-0 bottom-0 p-5 md:p-8">
          <h3 key={`t${i}${lang}`} className="tour-in text-2xl font-semibold md:text-4xl">{scene.title[lang]}</h3>
          <p key={`s${i}${lang}`} className="tour-in mt-2 max-w-3xl text-sm leading-relaxed text-white/85 md:text-base">{scene.say[lang]}</p>
        </div>
        {!playing && (
          <button onClick={() => setPlaying(true)} className="absolute left-1/2 top-1/2 grid size-20 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white/90 text-black shadow-2xl" aria-label="Play tour">
            <Play className="ml-1 size-8 fill-current" />
          </button>
        )}
      </div>
      <div className="flex h-1 bg-white/10">
        {SCENES_.map((_, k) => <span key={k} className={cn("flex-1 border-r border-black/50 transition-colors", k <= i ? "bg-[var(--primary)]" : "")} />)}
      </div>
      <div className="flex flex-wrap items-center gap-2 p-3">
        <Button size="sm" variant="ghost" className="text-white hover:bg-white/10" onClick={() => setI((n) => Math.max(0, n - 1))} aria-label="Previous"><ChevronLeft /></Button>
        <Button size="sm" variant="ghost" className="text-white hover:bg-white/10" onClick={() => setPlaying((p) => !p)} aria-label={playing ? "Pause" : "Play"}>{playing ? <Pause /> : <Play />}</Button>
        <Button size="sm" variant="ghost" className="text-white hover:bg-white/10" onClick={() => setI((n) => Math.min(SCENES_.length - 1, n + 1))} aria-label="Next"><ChevronRight /></Button>
        <Button size="sm" variant="ghost" className="text-white hover:bg-white/10" onClick={() => setMuted((m) => !m)} aria-label={muted ? "Unmute" : "Mute"}>{muted ? <VolumeX /> : <Volume2 />}</Button>
        <div className="flex flex-wrap gap-1">
          {(englishOnly ? LANGS.filter((l) => l.id === "en") : LANGS).map((l) => (
            <button key={l.id} onClick={() => setLang(l.id)} className={cn("rounded-full px-3 py-1 text-xs", lang === l.id ? "bg-white text-black" : "bg-white/10 hover:bg-white/20")}>{l.label}</button>
          ))}
        </div>
        {voices.length > 0 && (
          <select value={voiceName} onChange={(e) => setVoiceName(e.target.value)} className="max-w-48 rounded-full bg-white/10 px-3 py-1 text-xs" aria-label="Voice">
            <option value="" className="text-black">Saige studio voice (natural)</option>
            {voices.map((v) => <option key={v.name} value={v.name} className="text-black">{v.name.replace(/Microsoft |Google | Online \(Natural\)/g, "")}</option>)}
          </select>
        )}
        <div className="ml-auto flex gap-2">
          {rec ? <Button size="sm" variant="secondary" onClick={() => rec.stop()}><Square /> Stop & download</Button>
            : <Button size="sm" variant="secondary" onClick={() => void record()}><Download /> Record video</Button>}
        </div>
      </div>
      {recErr && (
        <p className="px-4 pb-3 text-xs text-white/60">
          {recErr ?? `No ${L.label} voice is installed on this device, so the tour plays with captions only. Tip: open Saige in Microsoft Edge for natural neural voices in all six languages, or add a voice in Windows Settings → Time & language → Speech.`}
        </p>
      )}
    </div>
  );
}
