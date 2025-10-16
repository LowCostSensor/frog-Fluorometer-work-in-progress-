#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <SD.h>
#include <SPI.h>
#include <WiFiUdp.h>
#include <NTPClient.h>
#include <esp_task_wdt.h>

// ------------------- CONFIG -------------------
const char* WIFI_SSID = "___";            // Your WiFi SSID
const char* WIFI_PASSWORD = "___";        // Your WiFi password
const char* THINGSPEAK_URL = "http://api.thingspeak.com/update";
const char* THINGSPEAK_WRITE_KEY = "GHRZMABOQG7DIAWQ";
const int SD_CS_PIN = 18;                 // SD card chip select pin

const int LED_CHLOROPHYLL = 5;            // LED for chlorophyll (430nm)
const int LED_HUMIC = 4;                  // LED for humic substances (280nm)
const int LDR_PIN = 36;                   // LDR pin to read light

const unsigned long MEASUREMENT_INTERVAL_MS = 10UL * 60UL * 1000UL; // 10 minutes
const float LDR_GAMMA = 0.7;              // LDR gamma correction
const float LDR_RL10 = 50;                // Reference resistor (kOhm)
const float LDR_FIXED = 2;                // Fixed resistor in voltage divider (kOhm)

WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org", 3600); // NTP client for timestamps

#define WDT_TIMEOUT_SECONDS 60            // Watchdog timeout

// ------------------- SETUP -------------------
void setup() {
  Serial.begin(115200);

  // Setup pins
  pinMode(LED_CHLOROPHYLL, OUTPUT);
  pinMode(LED_HUMIC, OUTPUT);

  // Initialize watchdog
  esp_task_wdt_init(WDT_TIMEOUT_SECONDS, true);
  esp_task_wdt_add(NULL);

  // Connect to WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  unsigned long startTime = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startTime < 15000) {
    Serial.print(".");
    delay(500);
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? "\nWiFi connected" : "\nWiFi not connected");

  // Start NTP client
  timeClient.begin();
  timeClient.update();

  // Initialize SD card
  if (!SD.begin(SD_CS_PIN)) {
    Serial.println("SD card initialization failed!");
  } else {
    Serial.println("SD card initialized successfully");
  }
}

// ------------------- HELPER FUNCTIONS -------------------
// Read LDR and convert to "lux" value
float readLux() {
  int raw = analogRead(LDR_PIN);
  float voltage = raw / 4095.0 * 3.3;
  if (voltage < 0.01) voltage = 0.01;  // avoid division by zero
  float resistance = LDR_FIXED * 1000.0 * voltage / (3.3 - voltage);
  float lux = pow(LDR_RL10 * 1000.0 * pow(10.0, LDR_GAMMA) / resistance, 1.0 / LDR_GAMMA);
  return lux;
}

// Convert lux reading to chlorophyll concentration (placeholder)
float calibrateChlorophyll(float lux) {
  return lux * 0.5;
}

// Convert lux reading to humic substance concentration (placeholder)
float calibrateHumic(float lux) {
  return 0.01 * lux * lux;
}

// ------------------- MAIN LOOP -------------------
void loop() {
  static unsigned long lastMeasurement = 0;

  // Reset watchdog
  esp_task_wdt_reset();

  // Take measurement every MEASUREMENT_INTERVAL_MS
  if (millis() - lastMeasurement >= MEASUREMENT_INTERVAL_MS) {
    lastMeasurement = millis();

    // Measure humic
    digitalWrite(LED_HUMIC, HIGH);
    delay(500); // allow LED to stabilize
    float humic = calibrateHumic(readLux());
    digitalWrite(LED_HUMIC, LOW);

    // Measure chlorophyll
    digitalWrite(LED_CHLOROPHYLL, HIGH);
    delay(500);
    float chl = calibrateChlorophyll(readLux());
    digitalWrite(LED_CHLOROPHYLL, LOW);

    // Print results
    Serial.printf("Measured Chlorophyll = %.2f ppb, Humic = %.2f ppb\n", chl, humic);

    // Send data to ThingSpeak if WiFi is connected
    if (WiFi.status() == WL_CONNECTED) {
      String url = String(THINGSPEAK_URL) + "?api_key=" + THINGSPEAK_WRITE_KEY +
                   "&field1=" + String(chl, 2) + "&field2=" + String(humic, 2);
      HTTPClient http;
      http.begin(url);
      int httpCode = http.GET();
      http.end();
      Serial.printf("ThingSpeak HTTP code: %d\n", httpCode);
    }
  }

  // Small delay to avoid busy looping
  delay(1000);
}
