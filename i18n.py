"""All user-facing texts in English, Hindi (Devanagari) and Hinglish (Hindi in Roman script).

First aid, prevention and formula texts are fixed on purpose: safety-critical advice
should not change from one LLM response to the next. Texts marked HTML are sent with
parse_mode=HTML, so "&" and "<" must be written as "&amp;" and "&lt;" there.
"""

from tbsa import AgeGroup, Depth, Region

LANGS = ("en", "hi", "hinglish")
DEFAULT_LANG = "en"

LANG_BUTTONS = {"en": "🇬🇧 English", "hi": "🇮🇳 हिन्दी", "hinglish": "🔤 Hinglish"}

# Instruction appended to the LLM prompts so answers come back in the chosen language.
LLM_LANGUAGE = {
    "en": "English",
    "hi": "Hindi written in Devanagari script (हिन्दी). Medicine names like paracetamol may stay in English",
    "hinglish": (
        "Hinglish: conversational Hindi written in Roman (English) letters, mixed with common English "
        "words, e.g. 'Jale hue hisse ko 20 minute tak thande behte paani mein rakhein.' Never use Devanagari"
    ),
}

CHOOSE_LANGUAGE = (
    "🌐 Please choose your language\n"
    "🌐 कृपया अपनी भाषा चुनें\n"
    "🌐 Apni bhasha chuniye"
)

T: dict[str, dict[str, str]] = {
    "language_set": {
        "en": "✅ Language: English",
        "hi": "✅ भाषा: हिन्दी",
        "hinglish": "✅ Language: Hinglish",
    },

    # ---------- reply-keyboard buttons ----------
    "btn_hospitals": {"en": "📍 Nearby hospitals", "hi": "📍 नज़दीकी अस्पताल", "hinglish": "📍 Paas ke hospital"},
    "btn_first_aid": {"en": "🩹 First aid", "hi": "🩹 प्राथमिक उपचार", "hinglish": "🩹 First aid"},
    "btn_prevention": {"en": "🛡 Prevention", "hi": "🛡 बचाव", "hinglish": "🛡 Bachav"},
    "btn_formula": {"en": "🧮 Burn % formula", "hi": "🧮 जलने का % फ़ॉर्मूला", "hinglish": "🧮 Burn % formula"},
    "btn_photo": {"en": "📸 Send a burn photo", "hi": "📸 फ़ोटो कैसे भेजें", "hinglish": "📸 Photo kaise bhejein"},
    "btn_language": {"en": "🌐 Language", "hi": "🌐 भाषा", "hinglish": "🌐 Bhasha"},
    "btn_share_location": {"en": "📍 Share My Live Location", "hi": "📍 मेरी लोकेशन भेजें", "hinglish": "📍 Meri Live Location Bhejiye"},

    # ---------- welcome / help (HTML) ----------
    "welcome": {
        "en": (
            "🏥 <b>CSJMU BurnCare Saathi</b>\n"
            "<i>In collaboration with CSJMU × MEDIOTECH</i>\n\n"
            "Instant, reliable burn first-aid guidance and emergency hospital support.\n\n"
            "👇 Ask a question below or choose an option:\n\n"
            "🌐 /language"
        ),
        "hi": (
            "🏥 <b>CSJMU BurnCare Saathi</b>\n"
            "<i>In collaboration with CSJMU × MEDIOTECH</i>\n\n"
            "जलने पर तुरंत और सही प्राथमिक उपचार व नज़दीकी अस्पताल सहायता।\n\n"
            "👇 नीचे अपना सवाल पूछें या कोई विकल्प चुनें:\n\n"
            "🌐 भाषा बदलें: /language"
        ),
        "hinglish": (
            "🏥 <b>CSJMU BurnCare Saathi</b>\n"
            "<i>In collaboration with CSJMU × MEDIOTECH</i>\n\n"
            "Instant, reliable burn first-aid guidance aur hospital support.\n\n"
            "👇 Niche apna sawal poochiye ya option chuniye:\n\n"
            "🌐 Bhasha badlein: /language"
        ),
    },
    "disclaimer": {
        "en": "⚠️ I am an automated assistant, not a doctor. My estimates from photos are rough. "
              "In an emergency, call {numbers} immediately.",
        "hi": "⚠️ मैं एक ऑटोमेटेड असिस्टेंट हूँ, डॉक्टर नहीं। फ़ोटो से मेरा अनुमान मोटा-मोटा होता है। "
              "इमरजेंसी में तुरंत {numbers} पर कॉल करें।",
        "hinglish": "⚠️ Main ek automated assistant hoon, doctor nahi. Photo se mera andaza approximate hota hai. "
                    "Emergency mein turant {numbers} par call karein.",
    },
    "privacy": {
        "en": "Photos and messages are sent to Google Gemini for analysis. Avoid including faces "
              "or identifying details if you can.",
        "hi": "फ़ोटो और मैसेज जाँच के लिए Google Gemini को भेजे जाते हैं। हो सके तो फ़ोटो में चेहरा "
              "या पहचान वाली चीज़ें न दिखाएँ।",
        "hinglish": "Photos aur messages analysis ke liye Google Gemini ko bheje jaate hain. Ho sake to photo "
                    "mein chehra ya pehchaan wali cheezein na dikhayein.",
    },
    "help": {
        "en": (
            "<b>Commands</b>\n"
            "/firstaid: burn first aid steps\n"
            "/prevention: how to avoid burns\n"
            "/formula: how burn % is calculated\n"
            "/photo: tips for sending a burn photo\n"
            "/hospitals &lt;city or area&gt;: hospitals near a place\n"
            "/parkland &lt;weight kg&gt;: Parkland fluid formula (for clinicians)\n"
            "/reset: start a new burn case\n"
            "/language: change language\n\n"
            "Or just type your burn question."
        ),
        "hi": (
            "<b>कमांड</b>\n"
            "/firstaid: जलने पर प्राथमिक उपचार\n"
            "/prevention: जलने से बचाव\n"
            "/formula: जलने का % कैसे निकालते हैं\n"
            "/photo: फ़ोटो भेजने के टिप्स\n"
            "/hospitals &lt;शहर या इलाक़ा&gt;: पास के अस्पताल\n"
            "/parkland &lt;वज़न kg&gt;: Parkland फ़्लूइड फ़ॉर्मूला (डॉक्टरों के लिए)\n"
            "/reset: नया केस शुरू करें\n"
            "/language: भाषा बदलें\n\n"
            "या सीधे जलने से जुड़ा अपना सवाल लिखें।"
        ),
        "hinglish": (
            "<b>Commands</b>\n"
            "/firstaid: jalne par first aid\n"
            "/prevention: jalne se bachav\n"
            "/formula: burn % kaise nikalte hain\n"
            "/photo: photo bhejne ke tips\n"
            "/hospitals &lt;shehar ya area&gt;: paas ke hospital\n"
            "/parkland &lt;wazan kg&gt;: Parkland fluid formula (doctors ke liye)\n"
            "/reset: naya case shuru karein\n"
            "/language: bhasha badlein\n\n"
            "Ya seedha burns se juda apna sawal likhiye."
        ),
    },

    # ---------- fixed medical texts (HTML) ----------
    "first_aid": {
        "en": """🩹 <b>Burn first aid — do this now</b>

1. <b>Stop the burning.</b> Move away from the heat source. If clothes are on fire: stop, drop and roll.
2. <b>Cool the burn</b> under cool running tap water for <b>20 minutes</b>. This still helps up to 3 hours after the burn.
3. <b>Remove</b> rings, bangles, watches, belts and clothing near the burn, unless stuck to the skin.
4. <b>Cover</b> loosely with cling film or a clean, non-fluffy cloth or plastic bag.
5. <b>Keep the person warm</b> (blanket), especially children, while cooling only the burned area.
6. <b>Pain relief:</b> paracetamol or ibuprofen as directed on the pack.

❌ <b>Do NOT</b>
• Use ice, ice water, ghee/butter, oil, toothpaste, egg, turmeric or any cream
• Burst blisters or peel off dead skin
• Pull off clothing stuck to the burn

⚡ <b>Electrical burn:</b> switch off the power before touching the person. Always go to hospital.
🧪 <b>Chemical burn:</b> brush off dry powder, remove contaminated clothing, rinse with running water for at least 20 minutes.

🚑 <b>Call {numbers} if:</b>
• The burn is large (bigger than the person's hand), deep, white or charred
• It is on the face, hands, feet, genitals or a joint
• There is difficulty breathing, smoke inhalation, a hoarse voice or soot around the nose/mouth
• It is an electrical or chemical burn
• The person is a child under 5, elderly, pregnant or has diabetes""",
        "hi": """🩹 <b>जलने पर तुरंत ये करें</b>

1. <b>जलना रोकें।</b> आग या गर्म चीज़ से दूर हटें। कपड़ों में आग लगे तो: रुकें, ज़मीन पर लेटें और लुढ़कें।
2. <b>ठंडा करें:</b> जले हिस्से को नल के ठंडे बहते पानी में <b>20 मिनट</b> तक रखें। जलने के 3 घंटे बाद तक भी यह फ़ायदेमंद है।
3. <b>हटाएँ:</b> अंगूठी, चूड़ी, घड़ी, बेल्ट और जले हिस्से के पास के कपड़े, अगर त्वचा से चिपके न हों।
4. <b>ढकें:</b> क्लिंग फ़िल्म (प्लास्टिक रैप) या साफ़, बिना रोएँ वाले कपड़े से ढीला ढकें।
5. <b>व्यक्ति को गर्म रखें</b> (कंबल से), ख़ासकर बच्चों को; सिर्फ़ जले हिस्से को ठंडा करें।
6. <b>दर्द के लिए:</b> पैकेट पर लिखी मात्रा के अनुसार पैरासिटामोल या आइबुप्रोफ़ेन।

❌ <b>ये बिल्कुल न करें</b>
• बर्फ़, बर्फ़ का पानी, घी/मक्खन, तेल, टूथपेस्ट, अंडा, हल्दी या कोई क्रीम न लगाएँ
• छाले न फोड़ें, जली त्वचा न छीलें
• त्वचा से चिपके कपड़े न खींचें

⚡ <b>बिजली से जलना:</b> व्यक्ति को छूने से पहले बिजली का मेन स्विच बंद करें। हमेशा अस्पताल जाएँ।
🧪 <b>केमिकल/तेज़ाब से जलना:</b> सूखा पाउडर झाड़ दें, केमिकल लगे कपड़े उतारें, कम से कम 20 मिनट बहते पानी से धोएँ।

🚑 <b>{numbers} पर कॉल करें अगर:</b>
• जला हिस्सा बड़ा है (व्यक्ति की हथेली से बड़ा), गहरा है, सफ़ेद या काला पड़ गया है
• चेहरे, हाथ, पैर, गुप्तांग या किसी जोड़ पर जला है
• साँस लेने में तकलीफ़ है, धुआँ अंदर गया है, आवाज़ भारी है या नाक/मुँह के पास कालिख है
• बिजली या केमिकल से जला है
• व्यक्ति 5 साल से छोटा बच्चा, बुज़ुर्ग, गर्भवती या डायबिटीज़ का मरीज़ है""",
        "hinglish": """🩹 <b>Jalne par turant ye karein</b>

1. <b>Jalna rokein.</b> Aag ya garam cheez se door hatein. Kapdon mein aag lage to: rukiye, zameen par letiye aur ludhakiye.
2. <b>Thanda karein:</b> jale hisse ko nal ke thande behte paani mein <b>20 minute</b> tak rakhein. Jalne ke 3 ghante baad tak bhi ye faydemand hai.
3. <b>Hatayein:</b> angoothi, choodi, ghadi, belt aur jale hisse ke paas ke kapde, agar skin se chipke na hon.
4. <b>Dhakein:</b> cling film (plastic wrap) ya saaf, bina rooein wale kapde se dheela dhakein.
5. <b>Insaan ko garam rakhein</b> (kambal se), khaaskar bachchon ko; sirf jale hisse ko thanda karein.
6. <b>Dard ke liye:</b> packet par likhi matra ke hisaab se paracetamol ya ibuprofen.

❌ <b>Ye bilkul na karein</b>
• Barf, barf ka paani, ghee/makhan, tel, toothpaste, anda, haldi ya koi cream na lagayein
• Chhale na phodein, jali skin na chheelein
• Skin se chipke kapde na kheenchein

⚡ <b>Bijli se jalna:</b> insaan ko chhoone se pehle bijli ka main switch band karein. Hamesha hospital jaayein.
🧪 <b>Chemical/tezaab se jalna:</b> sookha powder jhaad dein, chemical lage kapde utaarein, kam se kam 20 minute behte paani se dhoyein.

🚑 <b>{numbers} par call karein agar:</b>
• Jala hissa bada hai (insaan ki hatheli se bada), gehra hai, safed ya kaala pad gaya hai
• Chehre, haath, pair, genitals ya kisi joint par jala hai
• Saans lene mein dikkat hai, dhuaan andar gaya hai, awaaz bhaari hai ya naak/munh ke paas kaalikh hai
• Bijli ya chemical se jala hai
• Insaan 5 saal se chhota bachcha, buzurg, pregnant ya diabetes ka mareez hai""",
    },
    "prevention": {
        "en": """🛡 <b>Preventing burns</b>

<b>Kitchen</b>
• Turn pot handles inward; use back burners when children are around
• Never leave hot oil unattended; if oil catches fire, cover with a lid and turn off the gas. Never use water on an oil fire
• Keep children out of the kitchen while cooking; keep hot drinks away from table edges
• Check gas cylinders and pipes for leaks; turn off the regulator after use

<b>Hot water</b>
• Set geysers/water heaters to 50 °C or less
• Run cold water first, then add hot; test bath water with your elbow before bathing a child

<b>Fire</b>
• Install smoke alarms and keep a fire extinguisher at home
• Keep matches, lighters and firecrackers away from children; use firecrackers only outdoors with a bucket of water nearby
• Never sleep or leave the room with a candle, diya or heater burning

<b>Electrical</b>
• Don't overload sockets; replace damaged wires and plugs
• Use socket covers if you have small children; keep appliances away from water

<b>Chemicals</b>
• Store acids, cleaners and drain openers in labelled containers, out of children's reach
• Wear gloves and eye protection when handling them

<b>Sun</b>
• Use SPF 30+ sunscreen, cover up and avoid midday sun (11 am–3 pm)""",
        "hi": """🛡 <b>जलने से बचाव</b>

<b>रसोई</b>
• बर्तनों के हैंडल अंदर की तरफ़ रखें; बच्चे पास हों तो पीछे वाले चूल्हे का इस्तेमाल करें
• गर्म तेल को कभी अकेला न छोड़ें; तेल में आग लगे तो ढक्कन से ढकें और गैस बंद करें। तेल की आग पर कभी पानी न डालें
• खाना बनाते समय बच्चों को रसोई से दूर रखें; गर्म चाय/दूध मेज़ के किनारे पर न रखें
• गैस सिलेंडर और पाइप की लीकेज जाँचते रहें; इस्तेमाल के बाद रेगुलेटर बंद करें

<b>गर्म पानी</b>
• गीज़र का तापमान 50 °C या उससे कम रखें
• पहले ठंडा पानी डालें, फिर गर्म मिलाएँ; बच्चे को नहलाने से पहले कोहनी से पानी जाँचें

<b>आग</b>
• घर में स्मोक अलार्म और आग बुझाने का यंत्र रखें
• माचिस, लाइटर और पटाखे बच्चों की पहुँच से दूर रखें; पटाखे सिर्फ़ खुले में जलाएँ और पास में पानी की बाल्टी रखें
• जलती मोमबत्ती, दीया या हीटर छोड़कर न सोएँ, न कमरे से बाहर जाएँ

<b>बिजली</b>
• एक सॉकेट पर ज़्यादा प्लग न लगाएँ; ख़राब तार और प्लग बदलें
• छोटे बच्चे हों तो सॉकेट कवर लगाएँ; बिजली के उपकरण पानी से दूर रखें

<b>केमिकल</b>
• तेज़ाब, क्लीनर और ड्रेन क्लीनर लेबल लगे डिब्बों में, बच्चों की पहुँच से दूर रखें
• इन्हें इस्तेमाल करते समय दस्ताने और चश्मा पहनें

<b>धूप</b>
• SPF 30+ सनस्क्रीन लगाएँ, शरीर ढकें और दोपहर (11 बजे–3 बजे) की धूप से बचें""",
        "hinglish": """🛡 <b>Jalne se bachav</b>

<b>Kitchen</b>
• Bartanon ke handle andar ki taraf rakhein; bachche paas hon to peeche wale burner use karein
• Garam tel ko kabhi akela na chhodein; tel mein aag lage to dhakkan se dhakein aur gas band karein. Tel ki aag par kabhi paani na daalein
• Khana banate waqt bachchon ko kitchen se door rakhein; garam chai/doodh table ke kinare par na rakhein
• Gas cylinder aur pipe ki leakage check karte rahein; use ke baad regulator band karein

<b>Garam paani</b>
• Geyser ka temperature 50 °C ya usse kam rakhein
• Pehle thanda paani daalein, phir garam milayein; bachche ko nehlane se pehle kohni se paani check karein

<b>Aag</b>
• Ghar mein smoke alarm aur fire extinguisher rakhein
• Maachis, lighter aur patakhe bachchon ki pahunch se door rakhein; patakhe sirf khule mein jalayein aur paas mein paani ki balti rakhein
• Jalti mombatti, diya ya heater chhodkar na soyein, na kamre se bahar jaayein

<b>Bijli</b>
• Ek socket par zyada plug na lagayein; kharab taar aur plug badlein
• Chhote bachche hon to socket cover lagayein; bijli ke appliances paani se door rakhein

<b>Chemical</b>
• Tezaab, cleaner aur drain cleaner label lage dibbon mein, bachchon ki pahunch se door rakhein
• Inhe use karte waqt gloves aur chashma pehnein

<b>Dhoop</b>
• SPF 30+ sunscreen lagayein, body dhakein aur dopahar (11 baje–3 baje) ki dhoop se bachein""",
    },
    "formula": {
        "en": """🧮 <b>How burn percentage (%TBSA) is calculated</b>

Doctors measure burn size as a percentage of <b>Total Body Surface Area</b> (TBSA). Only partial-thickness (2nd degree) and full-thickness (3rd degree) burns are counted. Simple redness (1st degree) is not.

<b>1. Rule of Nines (adults)</b>
• Head and neck: 9%
• Each arm: 9%
• Front of trunk: 18%
• Back of trunk: 18%
• Each leg: 18%
• Genitals/perineum: 1%

<b>2. Lund &amp; Browder chart (all ages, used in burn units)</b>
Adjusts for age, because a child's head is relatively bigger and their legs smaller. Example: the whole head is 19% in an infant but 7% in an adult. <i>This bot uses Lund &amp; Browder.</i>

<b>3. Palm rule (small or scattered burns)</b>
The patient's own palm including fingers ≈ 1% TBSA.

<b>4. Parkland formula (for doctors, burns ≥20% adults / ≥10% children)</b>
IV fluid in first 24 h = 4 mL × body weight (kg) × %TBSA
Half in the first 8 hours from the time of the burn, the rest over the next 16 hours.
Use /parkland &lt;weight in kg&gt; after a photo assessment.""",
        "hi": """🧮 <b>जलने का प्रतिशत (%TBSA) कैसे निकालते हैं</b>

डॉक्टर जले हिस्से को <b>Total Body Surface Area</b> (TBSA, शरीर की कुल सतह) के प्रतिशत में नापते हैं। सिर्फ़ सेकंड डिग्री (आंशिक मोटाई) और थर्ड डिग्री (पूरी मोटाई) जलन गिनी जाती है। सिर्फ़ लालिमा (फ़र्स्ट डिग्री) नहीं गिनी जाती।

<b>1. Rule of Nines (वयस्कों के लिए)</b>
• सिर और गर्दन: 9%
• हर बाँह: 9%
• धड़ का आगे का हिस्सा: 18%
• धड़ का पीछे का हिस्सा: 18%
• हर पैर: 18%
• गुप्तांग: 1%

<b>2. Lund &amp; Browder चार्ट (हर उम्र के लिए, बर्न यूनिट में इस्तेमाल होता है)</b>
उम्र के हिसाब से बदलता है, क्योंकि बच्चे का सिर अनुपात में बड़ा और पैर छोटे होते हैं। उदाहरण: पूरा सिर शिशु में 19% पर वयस्क में 7% होता है। <i>यह बॉट Lund &amp; Browder इस्तेमाल करता है।</i>

<b>3. हथेली का नियम (छोटी या बिखरी जलन के लिए)</b>
मरीज़ की अपनी हथेली, उँगलियों समेत ≈ शरीर का 1%।

<b>4. Parkland फ़ॉर्मूला (डॉक्टरों के लिए; वयस्क ≥20%, बच्चे ≥10%)</b>
पहले 24 घंटे में IV फ़्लूइड = 4 mL × वज़न (kg) × %TBSA
आधा, जलने के समय से पहले 8 घंटे में; बाक़ी अगले 16 घंटे में।
फ़ोटो जाँच के बाद /parkland &lt;वज़न kg&gt; लिखें।""",
        "hinglish": """🧮 <b>Burn ka percentage (%TBSA) kaise nikalte hain</b>

Doctors jale hisse ko <b>Total Body Surface Area</b> (TBSA, body ki kul surface) ke percentage mein naapte hain. Sirf 2nd degree (partial thickness) aur 3rd degree (full thickness) burns gine jaate hain. Sirf laali (1st degree) nahi gini jaati.

<b>1. Rule of Nines (adults ke liye)</b>
• Sir aur gardan: 9%
• Har baanh: 9%
• Dhad ka aage ka hissa: 18%
• Dhad ka peeche ka hissa: 18%
• Har pair: 18%
• Genitals: 1%

<b>2. Lund &amp; Browder chart (har umar ke liye, burn units mein use hota hai)</b>
Umar ke hisaab se badalta hai, kyunki bachche ka sir proportion mein bada aur pair chhote hote hain. Example: poora sir baby mein 19% par adult mein 7% hota hai. <i>Ye bot Lund &amp; Browder use karta hai.</i>

<b>3. Hatheli ka rule (chhote ya bikhre burns ke liye)</b>
Mareez ki apni hatheli, ungliyon samet ≈ body ka 1%.

<b>4. Parkland formula (doctors ke liye; adults ≥20%, bachche ≥10%)</b>
Pehle 24 ghante mein IV fluid = 4 mL × wazan (kg) × %TBSA
Aadha, jalne ke time se pehle 8 ghante mein; baaki agle 16 ghante mein.
Photo check ke baad /parkland &lt;wazan kg&gt; likhiye.""",
    },
    "photo_tips": {
        "en": """📸 <b>Sending a burn photo</b>
• Take the photo in good light, from about 30–50 cm away, showing the whole burn and some normal skin around it
• Add a caption saying the body part and side, e.g. "left forearm, front, hot oil"
• Send one photo per body area. I add them up into one case
• Send /reset to start a new case for a different person

Cool the burn under running water for 20 minutes <b>before</b> taking photos.""",
        "hi": """📸 <b>जले हिस्से की फ़ोटो कैसे भेजें</b>
• अच्छी रोशनी में, लगभग 30–50 cm दूर से फ़ोटो लें; पूरा जला हिस्सा और आसपास की थोड़ी सामान्य त्वचा दिखे
• कैप्शन में शरीर का हिस्सा और साइड लिखें, जैसे "बायाँ हाथ, कलाई के ऊपर, गर्म तेल"
• हर हिस्से की अलग फ़ोटो भेजें। मैं सबको जोड़कर एक केस बनाता हूँ
• किसी दूसरे व्यक्ति के लिए नया केस शुरू करने को /reset भेजें

फ़ोटो लेने से <b>पहले</b> जले हिस्से को 20 मिनट बहते पानी में ठंडा करें।""",
        "hinglish": """📸 <b>Burn ki photo kaise bhejein</b>
• Achhi roshni mein, lagbhag 30–50 cm door se photo lijiye; poora jala hissa aur aaspaas ki thodi normal skin dikhe
• Caption mein body part aur side likhiye, jaise "left haath, kalai ke upar, garam tel"
• Har hisse ki alag photo bhejiye. Main sabko jodkar ek case banata hoon
• Kisi dusre insaan ke liye naya case shuru karne ko /reset bhejiye

Photo lene se <b>pehle</b> jale hisse ko 20 minute behte paani mein thanda karein.""",
    },
    "out_of_scope": {
        "en": "Sorry, I can only help with burn injuries: first aid, how serious a burn is, burn % estimation, "
              "wound care, prevention and finding a nearby hospital.\n\n"
              "Try asking something like \"What should I do for a hot oil burn?\" or send a photo of the burn.",
        "hi": "माफ़ कीजिए, मैं सिर्फ़ जलने की चोटों में मदद कर सकता हूँ: प्राथमिक उपचार, जलन कितनी गंभीर है, "
              "जलने का % अनुमान, घाव की देखभाल, बचाव और पास का अस्पताल ढूँढना।\n\n"
              "ऐसे पूछकर देखें: \"गर्म तेल से जलने पर क्या करें?\" या जले हिस्से की फ़ोटो भेजें।",
        "hinglish": "Sorry, main sirf burns mein madad kar sakta hoon: first aid, burn kitna serious hai, burn % ka "
                    "andaza, ghaav ki dekhbhaal, bachav aur paas ka hospital dhoondhna.\n\n"
                    "Aise poochiye: \"Garam tel se jalne par kya karein?\" ya burn ki photo bhejiye.",
    },

    # ---------- photo flow ----------
    "image_too_large": {
        "en": "That image is too large. Please send one under 10 MB.",
        "hi": "यह फ़ोटो बहुत बड़ी है। 10 MB से छोटी फ़ोटो भेजें।",
        "hinglish": "Ye photo bahut badi hai. 10 MB se chhoti photo bhejiye.",
    },
    "photo_failed": {
        "en": "Sorry, I couldn't analyse the photo right now (the free AI service may be busy). Please try again "
              "in a minute. Meanwhile: cool the burn under running water for 20 minutes. /firstaid",
        "hi": "माफ़ कीजिए, अभी फ़ोटो की जाँच नहीं हो पाई (मुफ़्त AI सेवा व्यस्त हो सकती है)। एक मिनट बाद फिर "
              "कोशिश करें। तब तक: जले हिस्से को 20 मिनट बहते पानी में रखें। /firstaid",
        "hinglish": "Sorry, abhi photo check nahi ho payi (free AI service busy ho sakti hai). Ek minute baad phir "
                    "try karein. Tab tak: jale hisse ko 20 minute behte paani mein rakhein. /firstaid",
    },
    "not_burn": {
        "en": "I couldn't see a burn injury in this photo. I can only assess burns. Try a clearer, well-lit photo "
              "of the burned skin, with a caption naming the body part. /photo",
        "hi": "इस फ़ोटो में मुझे जलने की चोट नहीं दिखी। मैं सिर्फ़ जलने की जाँच कर सकता हूँ। अच्छी रोशनी में "
              "साफ़ फ़ोटो भेजें और कैप्शन में शरीर का हिस्सा लिखें। /photo",
        "hinglish": "Is photo mein mujhe burn nahi dikha. Main sirf burns check kar sakta hoon. Achhi roshni mein "
                    "saaf photo bhejiye aur caption mein body part likhiye. /photo",
    },
    "age_question": {
        "en": "Got it. Body proportions change with age, so: <b>how old is the burned person?</b>",
        "hi": "ठीक है। उम्र के साथ शरीर का अनुपात बदलता है, इसलिए बताइए: <b>जले हुए व्यक्ति की उम्र कितनी है?</b>",
        "hinglish": "Theek hai. Umar ke saath body ka proportion badalta hai, isliye bataiye: "
                    "<b>jale hue insaan ki umar kitni hai?</b>",
    },
    "age_set": {"en": "Age group: {age}", "hi": "आयु वर्ग: {age}", "hinglish": "Age group: {age}"},
    "send_photo_first": {
        "en": "Please send a photo of the burn first.",
        "hi": "पहले जले हिस्से की फ़ोटो भेजें।",
        "hinglish": "Pehle burn ki photo bhejiye.",
    },
    "reset_done": {
        "en": "🆕 Started a new case. Send a burn photo or ask a question.",
        "hi": "🆕 नया केस शुरू। जले हिस्से की फ़ोटो भेजें या सवाल पूछें।",
        "hinglish": "🆕 Naya case shuru. Burn ki photo bhejiye ya sawal poochiye.",
    },

    # ---------- burn report (HTML) ----------
    "report_title": {
        "en": "🔥 <b>Burn assessment</b> (Lund &amp; Browder, {age})",
        "hi": "🔥 <b>जलने का आकलन</b> (Lund &amp; Browder, {age})",
        "hinglish": "🔥 <b>Burn assessment</b> (Lund &amp; Browder, {age})",
    },
    "burned_areas": {"en": "<b>Burned areas</b>", "hi": "<b>जले हुए हिस्से</b>", "hinglish": "<b>Jale hue hisse</b>"},
    "region_line": {
        "en": "• {region}: {fraction} of region, {depth} → {pct}%",
        "hi": "• {region}: उस हिस्से का {fraction}, {depth} → {pct}%",
        "hinglish": "• {region}: us hisse ka {fraction}, {depth} → {pct}%",
    },
    "tbsa_line": {
        "en": "📏 <b>Estimated TBSA: {tbsa}%</b> (2nd and 3rd degree burns)",
        "hi": "📏 <b>अनुमानित TBSA (शरीर का जला हिस्सा): {tbsa}%</b> (सेकंड और थर्ड डिग्री)",
        "hinglish": "📏 <b>Andazan TBSA: {tbsa}%</b> (2nd aur 3rd degree burns)",
    },
    "superficial_line": {
        "en": "   + {pct}% redness only (1st degree, not counted)",
        "hi": "   + {pct}% सिर्फ़ लालिमा (फ़र्स्ट डिग्री, गिनी नहीं जाती)",
        "hinglish": "   + {pct}% sirf laali (1st degree, count nahi hoti)",
    },
    "palm_check": {
        "en": "   Check: the patient's palm with fingers ≈ 1%.",
        "hi": "   जाँच: मरीज़ की उँगलियों समेत हथेली ≈ 1%।",
        "hinglish": "   Check: mareez ki ungliyon samet hatheli ≈ 1%.",
    },
    "level_emergency": {
        "en": "🚨 <b>EMERGENCY — call {numbers} or go to the nearest hospital NOW</b>",
        "hi": "🚨 <b>इमरजेंसी — अभी {numbers} पर कॉल करें या तुरंत नज़दीकी अस्पताल जाएँ</b>",
        "hinglish": "🚨 <b>EMERGENCY — abhi {numbers} par call karein ya turant paas ke hospital jaayein</b>",
    },
    "level_hospital": {
        "en": "🏥 <b>See a doctor / go to hospital today</b>",
        "hi": "🏥 <b>आज ही डॉक्टर को दिखाएँ / अस्पताल जाएँ</b>",
        "hinglish": "🏥 <b>Aaj hi doctor ko dikhayein / hospital jaayein</b>",
    },
    "level_home": {
        "en": "🏠 <b>Likely treatable at home</b> — see a doctor if it gets worse",
        "hi": "🏠 <b>शायद घर पर इलाज हो सकता है</b> — हालत बिगड़े तो डॉक्टर को दिखाएँ",
        "hinglish": "🏠 <b>Shayad ghar par ilaaj ho sakta hai</b> — haalat bigde to doctor ko dikhayein",
    },
    "reason_shock": {
        "en": "Burn area ≥{threshold}% — risk of burn shock; needs IV fluids in hospital",
        "hi": "जला हिस्सा ≥{threshold}% — बर्न शॉक का ख़तरा; अस्पताल में IV ड्रिप ज़रूरी",
        "hinglish": "Jala hissa ≥{threshold}% — burn shock ka khatra; hospital mein IV drip zaroori",
    },
    "reason_circumferential": {
        "en": "Burn goes all the way around a limb/chest — can cut off blood flow or breathing",
        "hi": "जलन हाथ/पैर/छाती के चारों ओर है — ख़ून का बहाव या साँस रुक सकती है",
        "hinglish": "Burn haath/pair/chhati ke chaaron taraf hai — khoon ka flow ya saans ruk sakti hai",
    },
    "reason_over10": {
        "en": "Partial-thickness burn larger than 10% of the body",
        "hi": "शरीर के 10% से ज़्यादा हिस्से में सेकंड डिग्री जलन",
        "hinglish": "Body ke 10% se zyada hisse mein 2nd degree burn",
    },
    "reason_full": {
        "en": "Full-thickness (3rd degree) burn — usually needs surgical care",
        "hi": "थर्ड डिग्री (पूरी मोटाई) जलन — आमतौर पर सर्जरी की ज़रूरत होती है",
        "hinglish": "3rd degree (full thickness) burn — aksar surgery ki zaroorat hoti hai",
    },
    "reason_deep": {
        "en": "Deep partial-thickness burn — may need specialist care",
        "hi": "गहरी सेकंड डिग्री जलन — विशेषज्ञ इलाज की ज़रूरत हो सकती है",
        "hinglish": "Gehra 2nd degree burn — specialist ilaaj ki zaroorat ho sakti hai",
    },
    "reason_special": {
        "en": "Burn on face, hands, feet or genitals",
        "hi": "चेहरे, हाथ, पैर या गुप्तांग पर जलन",
        "hinglish": "Chehre, haath, pair ya genitals par burn",
    },
    "reason_palm": {
        "en": "Blistered burn bigger than the person's palm (~1%)",
        "hi": "छालेदार जलन, व्यक्ति की हथेली (~1%) से बड़ी",
        "hinglish": "Chhale wala burn, insaan ki hatheli (~1%) se bada",
    },
    "reason_child5": {
        "en": "Child under 5 with a blistering burn",
        "hi": "5 साल से छोटे बच्चे को छालेदार जलन",
        "hinglish": "5 saal se chhote bachche ko chhale wala burn",
    },
    "reason_home": {
        "en": "Small superficial burn — usually treatable at home",
        "hi": "छोटी, सतही जलन — आमतौर पर घर पर इलाज हो सकता है",
        "hinglish": "Chhota, superficial burn — aksar ghar par ilaaj ho jaata hai",
    },
    "noticed": {"en": "⚠️ <b>Noticed in photo</b>", "hi": "⚠️ <b>फ़ोटो में दिखा</b>", "hinglish": "⚠️ <b>Photo mein dikha</b>"},
    "elec_chem": {
        "en": "⚡🧪 Electrical, chemical or smoke-inhalation burns always need hospital care, whatever the size.",
        "hi": "⚡🧪 बिजली, केमिकल या धुएँ से जलने पर, आकार चाहे जितना हो, हमेशा अस्पताल जाएँ।",
        "hinglish": "⚡🧪 Bijli, chemical ya dhuein se jalne par, size chahe jitna ho, hamesha hospital jaayein.",
    },
    "next_steps": {
        "en": "Next: cool under running water for 20 min (/firstaid), tap 📍 Nearby hospitals, or send more photos "
              "of other burned areas to add them. /reset for a new person.",
        "hi": "आगे: जले हिस्से को 20 मिनट बहते पानी में रखें (/firstaid), 📍 नज़दीकी अस्पताल दबाएँ, या दूसरे जले "
              "हिस्सों की फ़ोटो भेजें ताकि वे जुड़ सकें। नए व्यक्ति के लिए /reset।",
        "hinglish": "Aage: jale hisse ko 20 minute behte paani mein rakhein (/firstaid), 📍 Paas ke hospital dabayein, "
                    "ya dusre jale hisson ki photo bhejiye taaki wo jud sakein. Naye insaan ke liye /reset.",
    },

    # ---------- hospitals ----------
    "ask_place": {
        "en": "📍 <b>Find Nearby Hospitals &amp; Burn Centers</b>\n\n"
              "📱 <b>Mobile (iOS / Android):</b> Tap the button below to share live location.\n"
              "💻 <b>PC / Mac / Web:</b> Type your city or area name (e.g. <i>Kanpur</i>, <i>Lucknow</i>, <i>Delhi</i>):\n\n"
              "🚑 Emergency: {numbers}",
        "hi": "📍 <b>नज़दीकी अस्पताल और बर्न सेंटर</b>\n\n"
              "📱 <b>मोबाइल (iOS / Android):</b> नीचे दिए गए बटन से लोकेशन शेयर करें।\n"
              "💻 <b>कंप्यूटर / Mac / लैपटॉप:</b> अपने शहर या इलाक़े का नाम लिखें (जैसे <i>Kanpur</i>, <i>Lucknow</i>, <i>Delhi</i>):\n\n"
              "🚑 इमरजेंसी: {numbers}",
        "hinglish": "📍 <b>Paas ke Hospital &amp; Burn Centers</b>\n\n"
                    "📱 <b>Mobile (iOS / Android):</b> Neeche diye button se live location share karein.\n"
                    "💻 <b>PC / Mac / Laptop:</b> Apne shehar ya area ka naam likhiye (jaise <i>Kanpur</i>, <i>Lucknow</i>, <i>Delhi</i>):\n\n"
                    "🚑 Emergency: {numbers}",
    },
    "place_not_found": {
        "en": "I couldn't find \"{place}\" on the map. Try a nearby town or city name, e.g. Bihta, Patna, "
              "or share your location from your phone.",
        "hi": "मुझे नक्शे पर \"{place}\" नहीं मिला। पास के किसी शहर या क़स्बे का नाम लिखें, जैसे Bihta, Patna, "
              "या फ़ोन से अपनी लोकेशन भेजें।",
        "hinglish": "Mujhe map par \"{place}\" nahi mila. Paas ke kisi shehar ya kasbe ka naam likhiye, jaise "
                    "Bihta, Patna, ya phone se apni location bhejiye.",
    },
    "your_location": {"en": "your location", "hi": "आपकी लोकेशन", "hinglish": "aapki location"},
    "hospitals_title": {
        "en": "🏥 <b>Hospitals near {where}</b>",
        "hi": "🏥 <b>{where} के पास के अस्पताल</b>",
        "hinglish": "🏥 <b>{where} ke paas ke hospital</b>",
    },
    "emergency_line": {
        "en": "🚑 Emergency: <b>{numbers}</b>",
        "hi": "🚑 इमरजेंसी: <b>{numbers}</b>",
        "hinglish": "🚑 Emergency: <b>{numbers}</b>",
    },
    "kind_hospital": {"en": "Hospital", "hi": "अस्पताल", "hinglish": "Hospital"},
    "kind_clinic": {"en": "Clinic", "hi": "क्लिनिक", "hinglish": "Clinic"},
    "tag_burn": {
        "en": "🔥 Burn/plastic surgery unit · ",
        "hi": "🔥 बर्न/प्लास्टिक सर्जरी यूनिट · ",
        "hinglish": "🔥 Burn/plastic surgery unit · ",
    },
    "tag_major": {
        "en": "⭐ Major/government hospital · ",
        "hi": "⭐ बड़ा/सरकारी अस्पताल · ",
        "hinglish": "⭐ Bada/sarkari hospital · ",
    },
    "directions": {"en": "🧭 Directions", "hi": "🧭 रास्ता देखें", "hinglish": "🧭 Rasta dekhein"},
    "hospitals_footer": {
        "en": "For serious burns, a large government or medical-college hospital is more likely to have a burn "
              "unit. Call ahead if you can. Data: © OpenStreetMap contributors.",
        "hi": "गंभीर जलन में बड़े सरकारी या मेडिकल कॉलेज अस्पताल में बर्न यूनिट होने की संभावना ज़्यादा होती है। "
              "हो सके तो पहले फ़ोन कर लें। डेटा: © OpenStreetMap contributors.",
        "hinglish": "Serious burn mein bade sarkari ya medical college hospital mein burn unit hone ki sambhavna "
                    "zyada hoti hai. Ho sake to pehle phone kar lein. Data: © OpenStreetMap contributors.",
    },
    "map_down": {
        "en": "Sorry, the map service is not responding. For an emergency call {numbers}.",
        "hi": "माफ़ कीजिए, नक्शा सेवा अभी जवाब नहीं दे रही। इमरजेंसी में {numbers} पर कॉल करें।",
        "hinglish": "Sorry, map service abhi jawab nahi de rahi. Emergency mein {numbers} par call karein.",
    },
    "no_hospitals": {
        "en": "I couldn't find hospitals within 30 km of {where}. Call {numbers} for an ambulance.",
        "hi": "{where} के 30 km के अंदर कोई अस्पताल नहीं मिला। एम्बुलेंस के लिए {numbers} पर कॉल करें।",
        "hinglish": "{where} ke 30 km ke andar koi hospital nahi mila. Ambulance ke liye {numbers} par call karein.",
    },

    # ---------- errors ----------
    "llm_down": {
        "en": "Sorry, I'm having trouble reaching the AI service. Please try again shortly.\n"
              "If this is an emergency, call {numbers}. For first aid see /firstaid.",
        "hi": "माफ़ कीजिए, अभी AI सेवा से जुड़ने में दिक्कत है। थोड़ी देर बाद फिर कोशिश करें।\n"
              "इमरजेंसी हो तो {numbers} पर कॉल करें। प्राथमिक उपचार के लिए /firstaid देखें।",
        "hinglish": "Sorry, abhi AI service se judne mein dikkat hai. Thodi der baad phir try karein.\n"
                    "Emergency ho to {numbers} par call karein. First aid ke liye /firstaid dekhiye.",
    },
    "generic_error": {
        "en": "Something went wrong. If this is an emergency, call {numbers}.",
        "hi": "कुछ गड़बड़ हो गई। इमरजेंसी हो तो {numbers} पर कॉल करें।",
        "hinglish": "Kuch gadbad ho gayi. Emergency ho to {numbers} par call karein.",
    },
}

AGE_LABELS = {
    AgeGroup.UNDER_1: {"en": "Under 1 year", "hi": "1 साल से कम", "hinglish": "1 saal se kam"},
    AgeGroup.AGE_1_4: {"en": "1–4 years", "hi": "1–4 साल", "hinglish": "1–4 saal"},
    AgeGroup.AGE_5_9: {"en": "5–9 years", "hi": "5–9 साल", "hinglish": "5–9 saal"},
    AgeGroup.AGE_10_14: {"en": "10–14 years", "hi": "10–14 साल", "hinglish": "10–14 saal"},
    AgeGroup.AGE_15_17: {"en": "15–17 years", "hi": "15–17 साल", "hinglish": "15–17 saal"},
    AgeGroup.ADULT: {"en": "Adult (18+)", "hi": "वयस्क (18+)", "hinglish": "Adult (18+)"},
}

DEPTH_LABELS = {
    Depth.SUPERFICIAL: {
        "en": "Superficial (1st degree)", "hi": "सतही (फ़र्स्ट डिग्री)", "hinglish": "Superficial (1st degree)",
    },
    Depth.SUPERFICIAL_PARTIAL: {
        "en": "Superficial partial thickness (2nd degree)",
        "hi": "सतही आंशिक मोटाई (सेकंड डिग्री)",
        "hinglish": "Superficial partial thickness (2nd degree)",
    },
    Depth.DEEP_PARTIAL: {
        "en": "Deep partial thickness (2nd degree, deep)",
        "hi": "गहरी आंशिक मोटाई (सेकंड डिग्री, गहरी)",
        "hinglish": "Deep partial thickness (2nd degree, gehra)",
    },
    Depth.FULL_THICKNESS: {
        "en": "Full thickness (3rd degree)", "hi": "पूरी मोटाई (थर्ड डिग्री)", "hinglish": "Full thickness (3rd degree)",
    },
    Depth.UNCLEAR: {
        "en": "Depth unclear from photo", "hi": "फ़ोटो से गहराई साफ़ नहीं", "hinglish": "Photo se gehrai saaf nahi",
    },
}

# Region names are built from parts: "<part> (<side>, <face>)", e.g. "Forearm (left, front)".
_WHOLE_REGIONS = {
    Region.HEAD_FRONT: {"en": "Face", "hi": "चेहरा", "hinglish": "Chehra"},
    Region.HEAD_BACK: {"en": "Back of head", "hi": "सिर का पिछला हिस्सा", "hinglish": "Sir ka pichla hissa"},
    Region.NECK_FRONT: {"en": "Neck (front)", "hi": "गर्दन (आगे)", "hinglish": "Gardan (aage)"},
    Region.NECK_BACK: {"en": "Neck (back)", "hi": "गर्दन (पीछे)", "hinglish": "Gardan (peeche)"},
    Region.CHEST_ABDOMEN: {"en": "Chest and abdomen", "hi": "छाती और पेट", "hinglish": "Chhati aur pet"},
    Region.BACK: {"en": "Back", "hi": "पीठ", "hinglish": "Peeth"},
    Region.GENITALIA: {"en": "Genitals", "hi": "गुप्तांग", "hinglish": "Genitals"},
}
_PARTS = {
    "buttock": {"en": "Buttock", "hi": "नितंब", "hinglish": "Nitamb"},
    "upper_arm": {"en": "Upper arm", "hi": "ऊपरी बाँह", "hinglish": "Upari baanh"},
    "forearm": {"en": "Forearm", "hi": "अग्रबाहु", "hinglish": "Forearm"},
    "hand": {"en": "Hand", "hi": "हाथ", "hinglish": "Haath"},
    "thigh": {"en": "Thigh", "hi": "जाँघ", "hinglish": "Jaangh"},
    "lower_leg": {"en": "Lower leg", "hi": "पिंडली", "hinglish": "Pindli"},
    "foot": {"en": "Foot", "hi": "पैर का पंजा", "hinglish": "Pair ka panja"},
}
_SIDES = {
    "left": {"en": "left", "hi": "बाएँ", "hinglish": "left"},
    "right": {"en": "right", "hi": "दाएँ", "hinglish": "right"},
}
_FACES = {
    "front": {"en": "front", "hi": "आगे", "hinglish": "aage"},
    "back": {"en": "back", "hi": "पीछे", "hinglish": "peeche"},
    "palm": {"en": "palm", "hi": "हथेली", "hinglish": "hatheli"},
    "top": {"en": "top", "hi": "ऊपर", "hinglish": "upar"},
    "sole": {"en": "sole", "hi": "तलवा", "hinglish": "talwa"},
}


def t(lang: str, key: str, **kwargs) -> str:
    texts = T[key]
    text = texts.get(lang) or texts[DEFAULT_LANG]
    return text.format(**kwargs) if kwargs else text


def age_label(age: AgeGroup, lang: str) -> str:
    return AGE_LABELS[age].get(lang, AGE_LABELS[age][DEFAULT_LANG])


def depth_label(depth: Depth, lang: str) -> str:
    return DEPTH_LABELS[depth].get(lang, DEPTH_LABELS[depth][DEFAULT_LANG])


def region_name(region: Region, lang: str) -> str:
    if region in _WHOLE_REGIONS:
        return _WHOLE_REGIONS[region][lang]
    side, rest = region.value.split("_", 1)
    face = None
    for f in _FACES:
        if rest.endswith("_" + f):
            rest, face = rest[: -len(f) - 1], f
            break
    detail = _SIDES[side][lang] + (", " + _FACES[face][lang] if face else "")
    return f"{_PARTS[rest][lang]} ({detail})"


def button_actions() -> dict[str, str]:
    """Maps every language's button label to its action key, e.g. "🛡 बचाव" -> "btn_prevention"."""
    keys = ("btn_hospitals", "btn_first_aid", "btn_prevention", "btn_formula", "btn_photo", "btn_language")
    return {T[k][lang]: k for k in keys for lang in LANGS}
