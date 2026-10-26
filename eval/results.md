# Live evaluation: Haq Hisaab on Sarvam AI

- Work stories understood and wages computed correctly: **7/7**
- Real voice round-trip (Bulbul → Saaras → Sarvam-105B): **pass**
- Attendance-card photo read by Sarvam Vision: **pass**
- Explanation + employer letter + Labour Office complaint, all quoting the exact amount, spoken by Bulbul: **pass**

## Work stories (Sarvam-105B extraction → deterministic wage maths)

| Language | Story | Facts extracted | Owed | Expected | Result |
|---|---|---|---|---|---|
| Hindi | मैंने अक्टूबर में 26 दिन साइट पर काम किया, ठेकेदार ने 600 रुपये रोज़ बोला था, पर सिर्फ 12000 दिए। 20 घंटे ओवरटाइम का कुछ नहीं दिया। | days worked 26, daily rate 600, amount paid 12000, overtime hours 20 | ₹6600.0 | ₹6600 | ✅ |
| Hinglish | Bhaiya maine 20 din loading ka kaam kiya, roz ke saade paanch sau tay hue the, malik ne bas 8000 diye | days worked 20, daily rate 550, amount paid 8000 | ₹3000.0 | ₹3000 | ✅ |
| Tamil | நான் 22 நாள் கட்டிட வேலை செய்தேன், ஒரு நாளுக்கு 700 ரூபாய் சொன்னாங்க, ஆனா 11000 தான் கொடுத்தாங்க. | days worked 22, daily rate 700, amount paid 11000 | ₹4400.0 | ₹4400 | ✅ |
| Bengali (native digits, deduction) | আমি ২৪ দিন ইটভাটায় কাজ করেছি, রোজ ৪৫০ টাকা বলেছিল, কিন্তু ৮০০০ টাকা দিয়েছে, আর ১০০০ টাকা কেটে নিয়েছে। | days worked 24, daily rate 450, amount paid 8000, deductions 1000 | ₹2800.0 | ₹2800 | ✅ |
| Marathi (2 h/day overtime) | मी 25 दिवस शेतात काम केलं, रोज 400 ठरले होते, मालकाने फक्त 7000 दिले, आणि रोज 2 तास जास्त काम केलं. | days worked 25, daily rate 400, amount paid 7000, overtime hours 50 | ₹8000.0 | ₹8000 | ✅ |
| Telugu (monthly salary) | నేను ఇంటి పనిమనిషిగా నెలకు 7800 జీతానికి పని చేశాను, 26 రోజులు పని చేశాను, కానీ 5000 మాత్రమే ఇచ్చారు. | days worked 26, daily rate 300, amount paid 5000 | ₹2800.0 | ₹2800 | ✅ |
| English (paid in full) | I worked 10 days as a painter at 800 per day and the contractor paid me 8000. | days worked 10, daily rate 800, amount paid 8000 | ₹0.0 | ₹0 | ✅ |

## Voice round-trip

- Spoken: मैंने पंद्रह दिन काम किया, पाँच सौ रुपये रोज़ तय हुए थे, ठेकेदार ने सिर्फ पाँच हज़ार दिए।
- Heard by Saaras (hi-IN): मैंने पंद्रह दिन काम किया, पाँच सौ रुपये रोज़ तय हुए थे, ठेकेदार ने सिर्फ़ पाँच हज़ार दिए।
- Facts: days worked 15, daily rate 500, amount paid 5000 → owed ₹2500.0 ✅

## Sarvam Vision: attendance card ([samples/attendance_card.jpg](../samples/attendance_card.jpg))

- Facts read from the photo: days worked 26, daily rate 600, amount paid 12000, overtime hours 20 ✅ (5623 ms)

<details><summary>Text Sarvam Vision extracted</summary>

```
हाज़री कार्ड / ATTENDANCE CARD
ठेकेदार: रमेश कंस्ट्रक्शन, हडपसर साइट, पुणे
मज़दूर का नाम: राजू यादव माह: अक्टूबर 2026
मज़दूरी दर: ₹600 परतदिनि (8 घंटे)

01/10 P
02/10 P
03/10 P +2 घंटे
04/10 P +2 घंटे
05/10 A
06/10 P
07/10 P
08/10 P
09/10 P
10/10 P +2 घंटे
11/10 P +2 घंटे
12/10 A
13/10 P
14/10 P
15/10 P
16/10 P
17/10 P +2 घंटे
18/10 P +2 घंटे
19/10 A
20/10 P
21/10 P
22/10 P
23/10 P
24/10 P +2 घंटे
25/10 P +2 घंटे
26/10 A
27/10 P
28/10 P
29/10 P +2 घंटे
30/10 P +2 घंटे

कुल हाज़री: 26 दनि
ओवरटाइम: 20 घंटे
भुगतान मिला: ₹12,000 (नकद)

हस्ताक्षर ठेकेदार: ___________ मज़दूर: अंगूठा
```
</details>

## Claim output (Hindi)

**Spoken explanation:** राजू जी, आपने अक्टूबर 2026 में 26 दिन काम किया और आपकी कुल कमाई ₹18600 बनी है। आपको अब तक सिर्फ ₹12000 मिले हैं, इसलिए अभी भी ₹6600 बकाया है। इसमें ₹15600 आपकी तय दिहाड़ी के हैं और ₹3000 ओवरटाइम के हैं, जो कानून के तहत दोगुने मिलते हैं। सबसे पहले आप अपने मालिक रमेश कंस्ट्रक्शन को यह पत्र देकर पैसे मांगें। अगर 7 दिन में पैसे नहीं मिलते, तो आप जिले के श्रम कार्यालय में शिकायत करें। मुफ्त कानूनी मदद के लिए आप NALSA हेल्पलाइन 15100 पर कॉल कर सकते हैं।

<details><summary>Letter to employer</summary>

```
सेवा में, रमेश कंस्ट्रक्शन,

विषय: अक्टूबर 2026 के बकाया वेतन के भुगतान के संबंध में

महोदय, मैंने अक्टूबर 2026 में आपके यहाँ 26 दिन काम किया है। मेरी कुल कमाई ₹18600 थी, जिसमें से मुझे सिर्फ ₹12000 मिले हैं। इसलिए मेरा ₹6600 का वेतन बकाया है। इसमें ₹15600 मेरी 26 दिन की दिहाड़ी के हैं और ₹3000 ओवरटाइम के हैं, जो कानून के अनुसार दोगुने मिलते हैं। कृपया मेरा पूरा बकाया वेतन 7 दिन के अंदर दे दें।

धन्यवाद,
Raju Yadav
[तारीख] [हस्ताक्षर]
```
</details>

<details><summary>Complaint to Labour Office</summary>

```
To,
The Inspector-cum-Facilitator / Assistant Labour Commissioner,
District Labour Office,
[District Name]

Subject: Complaint for non-payment of wages and overtime under the Code on Wages, 2019

Respected Sir/Madam,

I, Raju Yadav, am a daily-wage worker who worked at Ramesh Construction in [Work Place] during October 2026. I worked for 26 days at a daily rate of ₹600 and also worked 20 hours of overtime. However, my employer has only paid me ₹12000, leaving a balance of ₹6600 unpaid.

Wage Calculation:
- Agreed wages: 26 days × ₹600 = ₹15600
- Overtime: 20 h × ₹75/h × 2 = ₹3000
- Total Earned: ₹18600
- Amount Received: -₹12000
- Amount Owed: ₹6600

I request you to kindly direct the employer, Ramesh Construction, to pay my full pending wages of ₹6600 immediately. If the employer fails to pay, please take strict legal action against them as per the Code on Wages, 2019.

Date: [Date]
Signature: _____________________
Name: Raju Yadav
Contact: [Phone Number]
```
</details>

API usage for this run: `{"stt_calls": 1, "chat_calls": 10, "tts_calls": 2, "tts_chars": 540, "vision_pages": 1, "cache_hits": 0}`
