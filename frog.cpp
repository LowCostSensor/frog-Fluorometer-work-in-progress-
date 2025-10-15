#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

// --- WiFi credentials ---
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// --- ThingSpeak ---
const char* server = "http://api.thingspeak.com/update";
const char* apiKey = "GHRZMABOQG7DIAWQ"; // write API key

// --- LDR constants ---
const float GAMMA = 0.7;
const float RL10  = 50;
const float R_FIXED = 2;

// --- Pin definitions ---
const int LED_430 = 5;     // 430nm LED (chlorophyll)
const int LED_280 = 4;     // 280nm LED (fDOM)
const int LDR1_PIN = 36;   // ADC1_CH0

// --- Fake calibration curves ---
float calibrateChlorophyll(float lux) {
  // fake: linear ppb = 0.5 * lux
  return lux * 0.5;
}

float calibrateHumic(float lux) {
  // fake: quadratic ppb = 0.01 * lux^2
  return 0.01 * lux * lux;
}

// --- Read LDR and compute lux ---
float read_LDR() {
  int analogLDR1 = analogRead(LDR1_PIN);
  float voltage = analogLDR1 / 4095.0 * 3.3;
  float resistance = R_FIXED * 1000 * voltage / (3.3 - voltage);
  float lux = pow(RL10 * 1000 * pow(10, GAMMA) / resistance, 1 / GAMMA);
  return lux;
}

// --- Send to ThingSpeak ---
void sendThingSpeak(float chlorophyll_ppb, float humic_ppb) {
  if(WiFi.status() == WL_CONNECTED){
    HTTPClient http;

    String url = String(server) + "?api_key=" + apiKey;
    url += "&field1=" + String(chlorophyll_ppb,2);
    url += "&field2=" + String(humic_ppb,2);

    http.begin(url);
    int httpCode = http.GET();
    if(httpCode > 0){
      Serial.printf("ThingSpeak update: %d\n", httpCode);
    } else {
      Serial.printf("Error sending to ThingSpeak: %s\n", http.errorToString(httpCode).c_str());
    }
    http.end();
  } else {
    Serial.println("WiFi not connected");
  }
}

// --- LED cycles ---
void measureChlorophyll() {
  digitalWrite(LED_430, HIGH);
  delay(500);
  float lux = read_LDR();
  float ppb = calibrateChlorophyll(lux);
  Serial.print("[Chlorophyll] Lux: "); Serial.print(lux); Serial.print(" -> ppb: "); Serial.println(ppb);
  sendThingSpeak(ppb, 0.0); // send chlorophyll, humic=0 for this measurement
  digitalWrite(LED_430, LOW);
  delay(1000);
}

void measureHumic() {
  digitalWrite(LED_280, HIGH);
  delay(500);
  float lux = read_LDR();
  float ppb = calibrateHumic(lux);
  Serial.print("[Humic] Lux: "); Serial.print(lux); Serial.print(" -> ppb: "); Serial.println(ppb);
  sendThingSpeak(0.0, ppb); // send humic, chlorophyll=0
  digitalWrite(LED_280, LOW);
  delay(1000);
}

// --- Setup ---
void setup() {
  Serial.begin(115200);
  pinMode(LED_430, OUTPUT);
  pinMode(LED_280, OUTPUT);

  // Connect WiFi
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);
  while(WiFi.status() != WL_CONNECTED){
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

// --- Main loop ---
void loop() {
  measureHumic();
  delay(2000);
  measureChlorophyll();
  delay(2000);
}
