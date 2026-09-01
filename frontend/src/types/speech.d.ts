// Web Speech API type declarations for TypeScript
interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  grammars: SpeechGrammarList;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  serviceURI: string;
  start(): void;
  stop(): void;
  abort(): void;
  onstart: ((this: SpeechRecognition, ev: Event) => unknown) | null;
  onend: ((this: SpeechRecognition, ev: Event) => unknown) | null;
  onresult: ((this: SpeechRecognition, ev: SpeechRecognitionEvent) => unknown) | null;
  onerror: ((this: SpeechRecognition, ev: SpeechRecognitionErrorEvent) => unknown) | null;
  onnomatch: ((this: SpeechRecognition, ev: SpeechRecognitionEvent) => unknown) | null;
  onaudiostart: ((this: SpeechRecognition, ev: Event) => unknown) | null;
  onaudioend: ((this: SpeechRecognition, ev: Event) => unknown) | null;
  onsoundstart: ((this: SpeechRecognition, ev: Event) => unknown) | null;
  onsoundend: ((this: SpeechRecognition, ev: Event) => unknown) | null;
  onspeechstart: ((this: SpeechRecognition, ev: Event) => unknown) | null;
  onspeechend: ((this: SpeechRecognition, ev: Event) => unknown) | null;
}

interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}

interface SpeechRecognitionResultList {
  readonly length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  readonly isFinal: boolean;
  readonly length: number;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionAlternative {
  readonly transcript: string;
  readonly confidence: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string;
  readonly message: string;
}

interface SpeechGrammarList {
  readonly length: number;
  item(index: number): SpeechGrammar;
  [index: number]: SpeechGrammar;
  addFromURI(src: string, weight?: number): void;
  addFromString(string: string, weight?: number): void;
}

interface SpeechGrammar {
  src: string;
  weight: number;
}

interface SpeechSynthesis extends EventTarget {
  readonly pending: boolean;
  readonly speaking: boolean;
  readonly paused: boolean;
  speak(utterance: SpeechSynthesisUtterance): void;
  cancel(): void;
  pause(): void;
  resume(): void;
  getVoices(): SpeechSynthesisVoice[];
  onvoiceschanged: ((this: SpeechSynthesis, ev: Event) => unknown) | null;
}

interface SpeechSynthesisUtterance extends EventTarget {
  text: string;
  lang: string;
  voice: SpeechSynthesisVoice | null;
  volume: number;
  rate: number;
  pitch: number;
  onstart: ((this: SpeechSynthesisUtterance, ev: Event) => unknown) | null;
  onend: ((this: SpeechSynthesisUtterance, ev: Event) => unknown) | null;
  onerror: ((this: SpeechSynthesisUtterance, ev: SpeechSynthesisErrorEvent) => unknown) | null;
  onpause: ((this: SpeechSynthesisUtterance, ev: Event) => unknown) | null;
  onresume: ((this: SpeechSynthesisUtterance, ev: Event) => unknown) | null;
  onboundary: ((this: SpeechSynthesisUtterance, ev: SpeechSynthesisEvent) => unknown) | null;
  onmark: ((this: SpeechSynthesisUtterance, ev: SpeechSynthesisEvent) => unknown) | null;
}

interface SpeechSynthesisVoice {
  readonly voiceURI: string;
  readonly name: string;
  readonly lang: string;
  readonly localService: boolean;
  readonly default: boolean;
}

interface SpeechSynthesisEvent extends Event {
  readonly charIndex: number;
  readonly elapsedTime: number;
  readonly name: string;
  readonly utterance: SpeechSynthesisUtterance;
}

interface SpeechSynthesisErrorEvent extends Event {
  readonly error: string;
}

interface Window {
  SpeechRecognition: {
    new (): SpeechRecognition;
  };
  webkitSpeechRecognition: {
    new (): SpeechRecognition;
  };
}
