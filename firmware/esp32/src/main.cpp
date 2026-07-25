#include <Arduino.h>
#include <math.h>

namespace {

constexpr char kFirmwareVersion[] = "0.3.0";
constexpr uint8_t kDacPin = 25;
constexpr uint8_t kAdcOutputPin = 34;
constexpr uint8_t kResistorSelectPins[] = {21, 22, 23};
constexpr uint8_t kCapacitorSwitchPins[] = {13, 14, 16, 17, 18, 19};
constexpr uint8_t kDacLow = 48;
constexpr uint8_t kDacHigh = 208;
constexpr size_t kTransientPoints = 42;
constexpr size_t kRepeats = 3;
constexpr uint32_t kMinimumDelayUs = 5;
constexpr uint32_t kMaximumDelayUs = 4000;
constexpr uint32_t kResetDelayUs = 4500;

struct StepFit {
  bool valid = false;
  float tauUs = 0.0F;
  float cutoffHz = 0.0F;
  float rSquared = 0.0F;
};

StepFit gLastFit;
uint8_t gResistorIndex = 0;
uint8_t gCapacitorMask = 1;

float median3(float a, float b, float c) {
  if (a > b) {
    const float temporary = a;
    a = b;
    b = temporary;
  }
  if (b > c) {
    const float temporary = b;
    b = c;
    c = temporary;
  }
  if (a > b) {
    const float temporary = a;
    a = b;
    b = temporary;
  }
  return b;
}

float readAveragedAdc(size_t samples = 16) {
  uint32_t total = 0;
  for (size_t index = 0; index < samples; ++index) {
    total += analogRead(kAdcOutputPin);
  }
  return static_cast<float>(total) / static_cast<float>(samples);
}

uint32_t logarithmicDelay(size_t index) {
  const float position =
      static_cast<float>(index) / static_cast<float>(kTransientPoints - 1);
  const float delay =
      expf(logf(static_cast<float>(kMinimumDelayUs)) +
           position *
               (logf(static_cast<float>(kMaximumDelayUs)) -
                logf(static_cast<float>(kMinimumDelayUs))));
  return static_cast<uint32_t>(lroundf(delay));
}

bool setConfiguration(uint8_t resistorIndex, uint8_t capacitorMask) {
  if (resistorIndex >= 6 || capacitorMask == 0 || capacitorMask >= 64) {
    return false;
  }
  for (size_t bit = 0; bit < 3; ++bit) {
    digitalWrite(
        kResistorSelectPins[bit],
        (resistorIndex & (1U << bit)) != 0 ? HIGH : LOW);
  }
  for (size_t bit = 0; bit < 6; ++bit) {
    digitalWrite(
        kCapacitorSwitchPins[bit],
        (capacitorMask & (1U << bit)) != 0 ? HIGH : LOW);
  }
  gResistorIndex = resistorIndex;
  gCapacitorMask = capacitorMask;
  delay(2);
  return true;
}

StepFit measureStepResponse() {
  float timesUs[kTransientPoints];
  float samples[kTransientPoints];

  dacWrite(kDacPin, kDacLow);
  delay(12);
  const float baseline = readAveragedAdc();
  dacWrite(kDacPin, kDacHigh);
  delay(12);
  const float finalValue = readAveragedAdc();
  const float span = finalValue - baseline;
  if (span < 120.0F) {
    return {};
  }

  for (size_t point = 0; point < kTransientPoints; ++point) {
    const uint32_t delayUs = logarithmicDelay(point);
    float repeated[kRepeats];
    for (size_t repeat = 0; repeat < kRepeats; ++repeat) {
      dacWrite(kDacPin, kDacLow);
      delayMicroseconds(kResetDelayUs);
      dacWrite(kDacPin, kDacHigh);
      delayMicroseconds(delayUs);
      repeated[repeat] = static_cast<float>(analogRead(kAdcOutputPin));
    }
    timesUs[point] = static_cast<float>(delayUs);
    samples[point] = median3(repeated[0], repeated[1], repeated[2]);
  }

  float sumX = 0.0F;
  float sumY = 0.0F;
  float sumXX = 0.0F;
  float sumXY = 0.0F;
  size_t used = 0;
  for (size_t point = 0; point < kTransientPoints; ++point) {
    const float normalized = (samples[point] - baseline) / span;
    if (normalized <= 0.08F || normalized >= 0.92F) {
      continue;
    }
    const float x = timesUs[point];
    const float y = logf(1.0F - normalized);
    sumX += x;
    sumY += y;
    sumXX += x * x;
    sumXY += x * y;
    ++used;
  }
  if (used < 8) {
    return {};
  }

  const float count = static_cast<float>(used);
  const float denominator = count * sumXX - sumX * sumX;
  if (fabsf(denominator) < 1.0e-6F) {
    return {};
  }
  const float slope = (count * sumXY - sumX * sumY) / denominator;
  const float intercept = (sumY - slope * sumX) / count;
  if (slope >= 0.0F) {
    return {};
  }
  const float tauUs = -1.0F / slope;

  const float meanY = sumY / count;
  float residualSquares = 0.0F;
  float totalSquares = 0.0F;
  for (size_t point = 0; point < kTransientPoints; ++point) {
    const float normalized = (samples[point] - baseline) / span;
    if (normalized <= 0.08F || normalized >= 0.92F) {
      continue;
    }
    const float observed = logf(1.0F - normalized);
    const float predicted = intercept + slope * timesUs[point];
    const float residual = observed - predicted;
    const float centered = observed - meanY;
    residualSquares += residual * residual;
    totalSquares += centered * centered;
  }
  const float rSquared =
      totalSquares > 1.0e-9F ? 1.0F - residualSquares / totalSquares : 0.0F;
  const bool valid =
      tauUs >= 5.0F && tauUs <= 5000.0F && rSquared >= 0.90F;
  const float cutoffHz =
      1000000.0F / (2.0F * static_cast<float>(PI) * tauUs);
  StepFit fit;
  fit.valid = valid;
  fit.tauUs = tauUs;
  fit.cutoffHz = cutoffHz;
  fit.rSquared = rSquared;
  return fit;
}

void printStep(const StepFit& fit) {
  if (!fit.valid) {
    Serial.println("ERR TRANSIENT_FIT_FAILED");
    return;
  }
  Serial.printf(
      "STEP TAU_US=%.3f FC_HZ=%.3f FIT_R2=%.5f\n",
      fit.tauUs,
      fit.cutoffHz,
      fit.rSquared);
}

void printSweep(float minimumHz, float maximumHz, int points) {
  if (minimumHz <= 0.0F || maximumHz <= minimumHz || points < 2 ||
      points > 64) {
    Serial.println("ERR INVALID_SWEEP");
    return;
  }
  gLastFit = measureStepResponse();
  if (!gLastFit.valid) {
    Serial.println("ERR TRANSIENT_FIT_FAILED");
    return;
  }

  Serial.print("SWEEP_DB ");
  const float logMinimum = logf(minimumHz);
  const float logMaximum = logf(maximumHz);
  for (int index = 0; index < points; ++index) {
    const float position =
        static_cast<float>(index) / static_cast<float>(points - 1);
    const float frequency =
        expf(logMinimum + position * (logMaximum - logMinimum));
    const float normalized = frequency / gLastFit.cutoffHz;
    const float gainDb = -10.0F * log10f(1.0F + normalized * normalized);
    if (index > 0) {
      Serial.print(',');
    }
    Serial.print(gainDb, 4);
  }
  Serial.println();
}

void handleCommand(String command) {
  command.trim();
  if (command == "ID?") {
    Serial.printf("ID DARWIN_ESP32_1 FW=%s\n", kFirmwareVersion);
    return;
  }
  if (command == "STATUS?") {
    Serial.printf(
        "STATUS MODE=STEP_MODEL TEMP_C=%.1f FC_HZ=%.3f FIT_R2=%.5f "
        "R=%u C=0x%02X\n",
        temperatureRead(),
        gLastFit.cutoffHz,
        gLastFit.rSquared,
        gResistorIndex,
        gCapacitorMask);
    return;
  }
  if (command == "STEP?") {
    gLastFit = measureStepResponse();
    printStep(gLastFit);
    return;
  }

  int resistorIndex = 0;
  unsigned int capacitorMask = 0;
  if (sscanf(
          command.c_str(),
          "SET R=%d C=%x",
          &resistorIndex,
          &capacitorMask) == 2) {
    if (!setConfiguration(
            static_cast<uint8_t>(resistorIndex),
            static_cast<uint8_t>(capacitorMask))) {
      Serial.println("ERR INVALID_CONFIGURATION");
      return;
    }
    Serial.println("OK");
    return;
  }

  float minimumHz = 0.0F;
  float maximumHz = 0.0F;
  int points = 0;
  if (sscanf(
          command.c_str(),
          "SWEEP %f %f %d",
          &minimumHz,
          &maximumHz,
          &points) == 3) {
    printSweep(minimumHz, maximumHz, points);
    return;
  }

  Serial.println("ERR UNKNOWN_COMMAND");
}

}  // namespace

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  analogSetPinAttenuation(kAdcOutputPin, ADC_11db);

  for (const uint8_t pin : kResistorSelectPins) {
    pinMode(pin, OUTPUT);
  }
  for (const uint8_t pin : kCapacitorSwitchPins) {
    pinMode(pin, OUTPUT);
  }
  setConfiguration(0, 1);
  dacWrite(kDacPin, kDacLow);
}

void loop() {
  if (!Serial.available()) {
    delay(1);
    return;
  }
  const String command = Serial.readStringUntil('\n');
  handleCommand(command);
}
