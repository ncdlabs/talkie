/**
 * AudioWorklet processor: float32 mono -> int16 at target rate, with RMS.
 * Replaces deprecated ScriptProcessorNode. Main thread receives { chunk, rms } per buffer.
 */
const TARGET_RATE = 16000;

class TalkieAudioProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const opts = (options && options.processorOptions) || {};
    this.contextSampleRate = opts.sampleRate || sampleRate || 16000;
    this.targetRate = opts.targetRate || TARGET_RATE;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input.length) return true;
    const channel = input[0];
    if (!channel || !channel.length) return true;
    const ratio = this.contextSampleRate / this.targetRate;
    const outLength = Math.floor(channel.length / ratio);
    const chunk = new Int16Array(outLength);
    let sumSq = 0;
    for (let i = 0; i < outLength; i++) {
      const idx = Math.floor(i * ratio);
      const v = channel[idx];
      chunk[i] = Math.max(-32768, Math.min(32767, v * 32767));
      sumSq += v * v;
    }
    const rms = outLength > 0 ? Math.sqrt(sumSq / outLength) : 0;
    this.port.postMessage({ chunk: chunk, rms: rms }, [chunk.buffer]);
    return true;
  }
}

registerProcessor('talkie-audio', TalkieAudioProcessor);
