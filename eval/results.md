# Live evaluation: Bolo Khata on Sarvam AI

Text entries parsed correctly: **14/14**  
Voice round-trips (Bulbul → Saaras → Sarvam-105B): **3/3**  
Reminders in the right script with the right amount: **4/4**

## Ledger parsing (Sarvam-105B)

| Language | Input | Parsed | Result | Latency |
|---|---|---|---|---|
| Hinglish | Ramesh ne 200 ka atta aur 50 ka tel udhaar liya | Ramesh credit ₹250 | ✅ | 1099 ms |
| Hindi | सुनीता ने तीन सौ रुपये वापस दिए | Sunita payment ₹300 | ✅ | 1083 ms |
| Hindi (dedh sau) | Mohan ne dedh sau ka doodh udhaar liya | Mohan credit ₹150 | ✅ | 1263 ms |
| Hindi (dhai sau) | Pinky ne dhai sau ki chini li, paise baad mein degi | Pinky credit ₹250 | ✅ | 1034 ms |
| Multi-customer | Raju ne 120 ka sabun udhaar liya aur Geeta ne 400 jama kiye | Raju credit ₹120; Geeta payment ₹400 | ✅ | 1417 ms |
| Tamil | குமார் 350 ரூபாய்க்கு அரிசி கடனாக வாங்கினார் | Kumar credit ₹350 | ✅ | 903 ms |
| Telugu | లక్ష్మి 500 రూపాయలు తిరిగి ఇచ్చింది | Lakshmi payment ₹500 | ✅ | 860 ms |
| Bengali (native digits) | রহিম ২০০ টাকার চাল বাকিতে নিয়েছে | Rahim credit ₹200 | ✅ | 799 ms |
| Marathi | सुरेशने 180 रुपयांचे तेल उधार घेतले | Suresh credit ₹180 | ✅ | 1028 ms |
| Kannada | ರವಿ 600 ರೂಪಾಯಿ ಬಾಕಿ ಹಣ ವಾಪಸ್ ಕೊಟ್ಟರು | Ravi payment ₹600 | ✅ | 858 ms |
| Gujarati | મહેશે 90 રૂપિયાની ખાંડ ઉધાર લીધી | Mahesh credit ₹90 | ✅ | 927 ms |
| Malayalam | അനിൽ 75 രൂപയുടെ പാൽ കടമായി വാങ്ങി | Anil credit ₹75 | ✅ | 941 ms |
| English | Fatima took milk and bread for 120 on credit | Fatima credit ₹120 | ✅ | 936 ms |
| Not a ledger entry | Aaj mausam bahut accha hai | (none) | ✅ | 684 ms |

## Voice round-trip (Bulbul v3 → Saaras v3 → Sarvam-105B)

| Language | Spoken | Heard (detected language) | Parsed | Result |
|---|---|---|---|---|
| Hindi voice | रमेश ने दो सौ पचास रुपये का आटा उधार लिया | रमेश ने दो सौ पचास रुपये का आटा उधार लिया। (hi-IN) | Ramesh credit ₹250 | ✅ |
| Tamil voice | குமார் முன்னூறு ரூபாய் திருப்பிக் கொடுத்தார் | குமார் முன்னூறு ரூபாய் திருப்பிக் கொடுத்தார். (ta-IN) | Kumar payment ₹300 | ✅ |
| Bengali voice | রহিম একশো টাকার চিনি বাকিতে নিয়েছে | রহিম ₹100-র চিনি বাকিতে নিয়েছে। (bn-IN) | Rahim credit ₹100 | ✅ |

## Reminders (Sarvam-105B)

| Language | Reminder | Native script | Result |
|---|---|---|---|
| Bengali | রমেশ বাবু, নমস্কার। আপনার গত সপ্তাহের আটা আর তেলের বিল ২৫০ টাকা বাকি আছে। সুবিধামতো সময় করে দোকানে এসে মিটিয়ে দেবেন। অনেক ধন্যবাদ। | 100% | ✅ |
| Telugu | నమస్కారం రమేష్ గారు, నేను శర్మ కిరాణా స్టోర్ నుండి మాట్లాడుతున్నాను. మీరు తీసుకున్న 250 రూపాయల అటా మరియు ఆయిల్ కి సంబంధించిన చిన్న బ్యాలెన్స్ ఉంది. మీకు వీలైనప్పుడు దయచేసి చెల్లించగలరు. ధన్యవాదాలు. | 100% | ✅ |
| Marathi | नमस्कार रमेश भाऊ! शर्मा किराणा स्टोअरमधून बोलतोय. मागच्या आठवड्यात घेतलेल्या 250 रुपयांच्या पिठाची आणि तेलाची बाकी होती. तुम्हाला वेळ मिळेल तेव्हा पेमेंट करून टाका. धन्यवाद! | 100% | ✅ |
| Kannada | ನಮಸ್ಕಾರ ರಮೇಶ್ ಅವರೇ, ನಮ್ಮ ಶರ್ಮ ಕಿರಾಣಾ ಸ್ಟೋರ್‌ನಿಂದ ನಿಮ್ಮ ತಿಂಗಳ ಸಾಮಾನುಗಳ ಬಿಲ್ 250 ರೂಪಾಯಿ ಬಾಕಿ ಇದೆ. ಇದು ನೀವು ತಂದ ಹಿಟ್ಟು ಮತ್ತು ಎಣ್ಣೆಯದ್ದಾಗಿದೆ. ದಯವಿಟ್ಟು ಬಿಡುವು ಮಾಡಿಕೊಂಡು ಆದಷ್ಟು ಬೇಗ ಪಾವತಿಸಿ. ಧನ್ಯವಾದಗಳು! | 100% | ✅ |

API usage for this run: `{"stt_calls": 3, "chat_calls": 21, "tts_calls": 3, "tts_chars": 120, "cache_hits": 0}`
