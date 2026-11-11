import { SupportedLanguage } from "../types";

export interface TranslationDictionary {
  appName: string;
  tagline: string;
  online: string;
  offline: string;
  newChat: string;
  newChatConfirmTitle: string;
  newChatConfirmText: string;
  confirm: string;
  cancel: string;
  welcomeGreeting: string;
  welcomeSub: string;
  welcomeInstruction: string;
  suggestedTitle: string;
  suggestions: {
    fertilizer: string;
    yellowLeaves: string;
    irrigation: string;
    marketPrice: string;
  };
  placeholder: string;
  tapToSpeak: string;
  listening: string;
  tapToStop: string;
  processingVoice: string;
  thinking: string;
  listenAloud: string;
  stopAudio: string;
  playingAudio: string;
  sourcesVerified: string;
  mandiRatesTitle: string;
  weatherTitle: string;
  viewDetails: string;
  modalPrice: string;
  minMaxPrice: string;
  temperature: string;
  humidity: string;
  windSpeed: string;
  chemicalSpray: string;
  micDenied: string;
  micUnsupported: string;
  noMicAvailable: string;
  emptyRecording: string;
  emptyTranscript: string;
  rateLimited: string;
  backendUnavailable: string;
  voiceError: string;
  synthesizingAudio: string;
  transcriptLabel: string;
  errorPrefix: string;
  send: string;
  helpful: string;
  notHelpful: string;
  feedbackPrompt: string;
  feedbackThanks: string;
  feedbackCommentPlaceholder: string;
  feedbackSubmit: string;
}

export const translations: Record<SupportedLanguage, TranslationDictionary> = {
  en: {
    appName: "FarmSaathi",
    tagline: "Your Agricultural AI Voice Assistant",
    online: "Online",
    offline: "Offline",
    newChat: "New Chat",
    newChatConfirmTitle: "Start New Conversation?",
    newChatConfirmText: "This will clear the current conversation history and start a fresh farmer session.",
    confirm: "Yes, Start New",
    cancel: "Cancel",
    welcomeGreeting: "Welcome to FarmSaathi! 🌾",
    welcomeSub: "Instant agricultural advice verified by ICAR and government packages of practices.",
    welcomeInstruction: "Tap the green microphone button below to speak your question, or tap any suggestion below to start:",
    suggestedTitle: "Common Farming Questions",
    suggestions: {
      fertilizer: "What fertilizer is suitable for my crop?",
      yellowLeaves: "Why are my crop leaves turning yellow?",
      irrigation: "When should I irrigate my field?",
      marketPrice: "What is today's market price?",
    },
    placeholder: "Type a farming question or tap mic...",
    tapToSpeak: "Tap to Speak",
    listening: "Listening... speak now",
    tapToStop: "Tap to Finish",
    processingVoice: "Analyzing speech with Sarvam AI...",
    thinking: "FarmSaathi is finding answers...",
    listenAloud: "Listen Aloud",
    stopAudio: "Stop Audio",
    playingAudio: "Playing...",
    sourcesVerified: "Verified ICAR & Official Sources",
    mandiRatesTitle: "Live AGMARKNET Mandi Rates",
    weatherTitle: "Live Agricultural Weather Advisory",
    viewDetails: "View Details",
    modalPrice: "Modal Rate",
    minMaxPrice: "Min / Max",
    temperature: "Temperature",
    humidity: "Humidity",
    windSpeed: "Wind",
    chemicalSpray: "Spray Safety Guidance",
    micDenied: "Microphone access was denied. Please allow microphone permissions in your browser or device settings.",
    micUnsupported: "Voice recording is not supported in this browser. Please use Chrome, Edge, Safari, or Firefox.",
    noMicAvailable: "No microphone detected on your device. You can type your question in the text box below.",
    emptyRecording: "Recording was too short or silent. Please tap the microphone and speak your question clearly.",
    emptyTranscript: "No clear speech detected. Please speak clearly near the microphone or type your question.",
    rateLimited: "Too many voice requests. Please wait a few moments before speaking again.",
    backendUnavailable: "FarmSaathi server is temporarily unavailable. Please try again shortly.",
    voiceError: "Voice processing failed. Please try again or type your question.",
    synthesizingAudio: "Preparing voice audio...",
    transcriptLabel: "Spoken question",
    errorPrefix: "Notice",
    send: "Send",
    helpful: "Helpful",
    notHelpful: "Not helpful",
    feedbackPrompt: "Was this answer helpful?",
    feedbackThanks: "Thank you for your feedback!",
    feedbackCommentPlaceholder: "How can we improve this answer? (optional)",
    feedbackSubmit: "Submit Feedback",
  },
  hi: {
    appName: "फार्मसाथी (FarmSaathi)",
    tagline: "आपका डिजिटल कृषि परामर्श साथी",
    online: "सक्रिय (ऑनलाइन)",
    offline: "ऑफ़लाइन",
    newChat: "नयी बातचीत",
    newChatConfirmTitle: "नयी बातचीत शुरू करें?",
    newChatConfirmText: "इससे पिछली बातचीत साफ हो जाएगी और नया सत्र शुरू होगा।",
    confirm: "हाँ, नया शुरू करें",
    cancel: "रद्द करें",
    welcomeGreeting: "फार्मसाथी में आपका स्वागत है! 🌾",
    welcomeSub: "भारतीय कृषि अनुसंधान परिषद (ICAR) द्वारा प्रमाणित सटीक कृषि सलाह।",
    welcomeInstruction: "अपनी भाषा में पूछने के लिए नीचे माइक बटन दबाएं, या किसी भी सवाल पर टैप करें:",
    suggestedTitle: "किसानों के प्रमुख सवाल",
    suggestions: {
      fertilizer: "मेरी फसल के लिए कौन सी खाद उपयुक्त है?",
      yellowLeaves: "फसल की पत्तियां पीली क्यों पड़ रही हैं?",
      irrigation: "खेत में सिंचाई कब करनी चाहिए?",
      marketPrice: "आज का मंडी भाव क्या है?",
    },
    placeholder: "खेती का सवाल यहाँ लिखें या माइक दबाएं...",
    tapToSpeak: "बोलने के लिए टैप करें",
    listening: "सुन रहा हूँ... बोलिए",
    tapToStop: "समाप्त करने के लिए दबाएं",
    processingVoice: "सर्वम एआई द्वारा आवाज़ समझी जा रही है...",
    thinking: "फार्मसाथी उत्तर खोज रहा है...",
    listenAloud: "आवाज़ में सुनें",
    stopAudio: "रोकें",
    playingAudio: "सुनाया जा रहा है...",
    sourcesVerified: "प्रमाणित ICAR एवं सरकारी स्रोत",
    mandiRatesTitle: "एगमार्कनेट दैनिक मंडी भाव",
    weatherTitle: "लाइव मौसम एवं कृषि परामर्श",
    viewDetails: "विवरण देखें",
    modalPrice: "मॉडल भाव",
    minMaxPrice: "न्यूनतम / अधिकतम",
    temperature: "तापमान",
    humidity: "नमी",
    windSpeed: "हवा",
    chemicalSpray: "दवा छिड़काव सुरक्षा नियम",
    micDenied: "माइक्रोफ़ोन की अनुमति नहीं मिली। कृपया ब्राउज़र सेटिंग्स में माइक्रोफ़ोन की अनुमति दें।",
    micUnsupported: "इस ब्राउज़र में आवाज़ रिकॉर्डिंग समर्थित नहीं है। कृपया क्रोम या एज ब्राउज़र का उपयोग करें।",
    noMicAvailable: "आपके उपकरण में कोई माइक्रोफ़ोन नहीं मिला। आप नीचे लिखकर पूछ सकते हैं।",
    emptyRecording: "रिकॉर्डिंग बहुत छोटी या शांत थी। कृपया माइक दबाकर स्पष्ट बोलें।",
    emptyTranscript: "कोई स्पष्ट आवाज़ सुनाई नहीं दी। कृपया माइक्रोफ़ोन के पास आकर बोलें।",
    rateLimited: "बहुत सारे अनुरोध प्राप्त हुए। कृपया कुछ क्षण प्रतीक्षा करें।",
    backendUnavailable: "सर्वर से संपर्क नहीं हो पा रहा है। कृपया कुछ देर बाद प्रयास करें।",
    voiceError: "आवाज़ समझने में त्रुटि हुई। आप नीचे लिखकर भी पूछ सकते हैं।",
    synthesizingAudio: "आवाज़ तैयार हो रही है...",
    transcriptLabel: "बोला गया सवाल",
    errorPrefix: "सूचना",
    send: "भेजें",
    helpful: "उपयोगी",
    notHelpful: "उपयोगी नहीं",
    feedbackPrompt: "क्या यह उत्तर उपयोगी था?",
    feedbackThanks: "आपकी प्रतिक्रिया के लिए धन्यवाद!",
    feedbackCommentPlaceholder: "हम इस उत्तर को कैसे बेहतर बना सकते हैं? (वैकल्पिक)",
    feedbackSubmit: "प्रतिक्रिया भेजें",
  },
  kn: {
    appName: "ಫಾರ್ಮ್‌ಸಾಥಿ (FarmSaathi)",
    tagline: "ನಿಮ್ಮ ಡಿಜಿಟಲ್ ಕೃಷಿ ಧ್ವನಿ ಸಹಾಯಕ",
    online: "ಆನ್‌ಲೈನ್",
    offline: "ಆಫ್‌ಲೈನ್",
    newChat: "ಹೊಸ ಸಂಭಾಷಣೆ",
    newChatConfirmTitle: "ಹೊಸ ಸಂಭಾಷಣೆ ಪ್ರಾರಂಭಿಸಬೇಕೆ?",
    newChatConfirmText: "ಇದು ಹಿಂದಿನ ಸಂಭಾಷಣೆಯನ್ನು ಅಳಿಸಿ ಹೊಸ ರೈತ ಸಂವಾದವನ್ನು ಪ್ರಾರಂಭಿಸುತ್ತದೆ.",
    confirm: "ಹೌದು, ಪ್ರಾರಂಭಿಸಿ",
    cancel: "ರದ್ದುಮಾಡಿ",
    welcomeGreeting: "ಫಾರ್ಮ್‌ಸಾಥಿಗೆ ಸುಸ್ವಾಗತ! 🌾",
    welcomeSub: "ICAR ಮತ್ತು ಕೃಷಿ ತಜ್ಞರಿಂದ ಪರಿಶೀಲಿಸಲ್ಪಟ್ಟ ವಿಶ್ವಾಸಾರ್ಹ ಸಲಹೆಗಳು.",
    welcomeInstruction: "ನಿಮ್ಮ ಭಾಷೆಯಲ್ಲಿ ಮಾತನಾಡಲು ಕೆಳಗಿನ ಮೈಕ್ರೋಫೋನ್ ಬಟನ್ ಟ್ಯಾಪ್ ಮಾಡಿ ಅಥವಾ ಪ್ರಶ್ನೆಯನ್ನು ಆರಿಸಿ:",
    suggestedTitle: "ಸಾಮಾನ್ಯ ಕೃಷಿ ಪ್ರಶ್ನೆಗಳು",
    suggestions: {
      fertilizer: "ನನ್ನ ಬೆಳೆಗೆ ಯಾವ ಗೊಬ್ಬರ ಸೂಕ್ತವಾಗಿದೆ?",
      yellowLeaves: "ಬೆಳೆಯ ಎಲೆಗಳು ಏಕೆ ಹಳದಿಯಾಗುತ್ತಿವೆ?",
      irrigation: "ಹೊಲಕ್ಕೆ ಯಾವಾಗ ನೀರುಣಿಸಬೇಕು?",
      marketPrice: "ಇಂದಿನ ಮಾರುಕಟ್ಟೆ ಬೆಲೆ ಎಷ್ಟು?",
    },
    placeholder: "ಕೃಷಿ ಪ್ರಶ್ನೆಯನ್ನು ಟೈಪ್ ಮಾಡಿ ಅಥವಾ ಮೈಕ್ ಬಳಸಿ...",
    tapToSpeak: "ಮಾತನಾಡಲು ಟ್ಯಾಪ್ ಮಾಡಿ",
    listening: "ಆಲಿಸುತ್ತಿದೆ... ಮಾತನಾಡಿ",
    tapToStop: "ಮುಗಿಸಲು ಟ್ಯಾಪ್ ಮಾಡಿ",
    processingVoice: "ಸರ್ವಂ AI ಮೂಲಕ ಧ್ವನಿ ಪ್ರಕ್ರಿಯೆಗೊಳಿಸಲಾಗುತ್ತಿದೆ...",
    thinking: "ಫಾರ್ಮ್‌ಸಾಥಿ ಉತ್ತರವನ್ನು ಸಿದ್ಧಪಡಿಸುತ್ತಿದೆ...",
    listenAloud: "ಉತ್ತರವನ್ನು ಆಲಿಸಿ",
    stopAudio: "ನಿಲ್ಲಿಸಿ",
    playingAudio: "ಆಲಿಸಲಾಗುತ್ತಿದೆ...",
    sourcesVerified: "ಪರಿಶೀಲಿಸಿದ ICAR ಹಾಗೂ ಅಧಿಕೃತ ಮೂಲಗಳು",
    mandiRatesTitle: "ಅಗಮಾರ್ಕ್‌ನೆಟ್ ಲೈವ್ ಮಾರುಕಟ್ಟೆ ದರಗಳು",
    weatherTitle: "ಹವಾಮಾನ ಹಾಗೂ ಕೃಷಿ ಸಲಹೆ",
    viewDetails: "ವಿವರಗಳನ್ನು ನೋಡಿ",
    modalPrice: "ಮಾದರಿ ಬೆಲೆ",
    minMaxPrice: "ಕನಿಷ್ಠ / ಗರಿಷ್ಠ",
    temperature: "ತಾಪಮಾನ",
    humidity: "ತೇವಾಂಶ",
    windSpeed: "ಗಾಳಿ",
    chemicalSpray: "ಸಿಂಪಡಣೆ ಸುರಕ್ಷತಾ ಮಾರ್ಗದರ್ಶನ",
    micDenied: "ಮೈಕ್ರೊಫೋನ್ ಅನುಮತಿ ಲಭ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ಬ್ರೌಸರ್ ಸೆಟ್ಟಿಂಗ್‌ಗಳಲ್ಲಿ ಮೈಕ್ರೊಫೋನ್ ಅನುಮತಿ ನೀಡಿ.",
    micUnsupported: "ಈ ಬ್ರೌಸರ್‌ನಲ್ಲಿ ಧ್ವನಿ ರೆಕಾರ್ಡಿಂಗ್ ಬೆಂಬಲಿಸುವುದಿಲ್ಲ. ದಯವಿಟ್ಟು Chrome ಅಥವಾ Edge ಬಳಸಿ.",
    noMicAvailable: "ನಿಮ್ಮ ಸಾಧನದಲ್ಲಿ ಮೈಕ್ರೊಫೋನ್ ಕಂಡುಬಂದಿಲ್ಲ. ದಯವಿಟ್ಟು ಕೆಳಗೆ ಟೈಪ್ ಮಾಡಿ ಪ್ರಶ್ನಿಸಿ.",
    emptyRecording: "ರೆಕಾರ್ಡಿಂಗ್ ತುಂಬಾ ಕಡಿಮೆಯಾಗಿದೆ. ದಯವಿಟ್ಟು ಮೈಕ್ ಒತ್ತಿ ಸ್ಪಷ್ಟವಾಗಿ ಮಾತನಾಡಿ.",
    emptyTranscript: "ಸ್ಪಷ್ಟ ಧ್ವನಿ ಕೇಳಿಸಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮೈಕ್ ಬಳಿ ಸ್ಪಷ್ಟವಾಗಿ ಮಾತನಾಡಿ.",
    rateLimited: "ಹೆಚ್ಚು ಧ್ವನಿ ವಿನಂತಿಗಳು ಬಂದಿವೆ. ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಸಮಯ ಕಾಯಿರಿ.",
    backendUnavailable: "ಸರ್ವರ್ ಸಂಪರ್ಕ ಸಾಧಿಸಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಪ್ರಯತ್ನಿಸಿ.",
    voiceError: "ಧ್ವನಿ ಪ್ರಕ್ರಿಯೆಗೊಳಿಸಲು ಸಾಧ್ಯವಾಗಿಲ್ಲ. ದಯವಿಟ್ಟು ಟೈಪ್ ಮಾಡಿ.",
    synthesizingAudio: "ಧ್ವನಿ ಉತ್ತರ ಸಿದ್ಧವಾಗುತ್ತಿದೆ...",
    transcriptLabel: "ಮಾತನಾಡಿದ ಪ್ರಶ್ನೆ",
    errorPrefix: "ಗಮನಿಸಿ",
    send: "ಕಳುಹಿಸಿ",
    helpful: "ಸಹಾಯಕವಾಗಿದೆ",
    notHelpful: "ಸಹಾಯಕವಾಗಿಲ್ಲ",
    feedbackPrompt: "ಈ ಉತ್ತರ ಸಹಾಯಕವಾಗಿದೆಯೇ?",
    feedbackThanks: "ನಿಮ್ಮ ಪ್ರತಿಕ್ರಿಯೆಗೆ ಧನ್ಯವಾದಗಳು!",
    feedbackCommentPlaceholder: "ಈ ಉತ್ತರವನ್ನು ಹೇಗೆ ಸುಧಾರಿಸಬಹುದು? (ಐಚ್ಛಿಕ)",
    feedbackSubmit: "ಪ್ರತಿಕ್ರಿಯೆ ಸಲ್ಲಿಸಿ",
  },
};
