class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._active = true;
    this.port.onmessage = (e) => {
      if (e.data === 'stop') this._active = false;
    };
  }
  process(inputs) {
    if (!this._active) return false;
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const float32 = input[0];
    const ratio   = sampleRate / 16000;
    const outLen  = Math.floor(float32.length / ratio);
    const int16   = new Int16Array(outLen);
    for (let i = 0; i < outLen; i++) {
      const s = Math.max(-1, Math.min(1, float32[Math.floor(i * ratio)]));
      int16[i] = s < 0 ? s * 32768 : s * 32767;
    }
    this.port.postMessage(int16.buffer, [int16.buffer]);
    return true;
  }
}
registerProcessor('pcm-processor', PCMProcessor);

