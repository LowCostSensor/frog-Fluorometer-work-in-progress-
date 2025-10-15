#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <SD.h>
#include <SPI.h>

// Setup wifi
const char* WIFI_SSID = "___";
const char* WIFI_PASSWORD = "___";

// Setup ThingSpeak
const char* THINGSPEAK_URL = "http://api.thingspeak.com/update";
const char* THINGSPEAK_WRITE_KEY = "GHRZMABOQG7DIAWQ";




// Pins for LEDs, LDR and SD card
const int LED_CHLOROPHYLL = 5;   // 430nm
const int LED_HUMIC = 4;         // 280nm
const int LDR_PIN = 36;
const int SD_CS_PIN = 18;

// LDR constants for lux calculation
const float LDR_GAMMA = 0.7;
const float LDR_RL10 = 50;       // kOhm
const float LDR_FIXED = 2;       // kOhm

// fake calibration curves for simulation
float calibrateChlorophyll(float lux) {
    // linear conversion: lux -> ppb
    return lux * 0.5;
}

float calibrateHumic(float lux) {
    // Quadratic conversion
    return 0.01 * lux * lux;
}

// Read LDR and convert to lux
float readLux() {
    int raw = analogRead(LDR_PIN);
    float voltage = raw / 4095.0 * 3.3;
    float resistance = LDR_FIXED * 1000 * voltage / (3.3 - voltage);
    return pow(LDR_RL10 * 1000 * pow(10, LDR_GAMMA) / resistance, 1.0 / LDR_GAMMA);
}

// Send data
void sendToThingSpeak(float chlorophyll, float humic) {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi not connected, skipping ThingSpeak update");
        return;
    }

    String url = String(THINGSPEAK_URL) + "?api_key=" + THINGSPEAK_WRITE_KEY;
    url += "&field1=" + String(chlorophyll, 2);
    url += "&field2=" + String(humic, 2);

    HTTPClient http;
    http.begin(url);
    int code = http.GET();
    if (code > 0) {
        Serial.printf("ThingSpeak response: %d\n", code);
    } else {
        Serial.printf("Failed to send to ThingSpeak: %s\n", http.errorToString(code).c_str());
    }
    http.end();
}

// Save data offline
void logToSD(float chlorophyll, float humic) {
    File file = SD.open("fluoro.csv", FILE_APPEND);
    if (!file) {
        Serial.println("Error opening SD file!");
        return;
    }
    file.print(millis());
    file.print(",");
    file.print(chlorophyll, 2);
    file.print(",");
    file.println(humic, 2);
    file.close();
}

void measureChlorophyll() {
    digitalWrite(LED_CHLOROPHYLL, HIGH);
    delay(500);

    float lux = readLux();
    float ppb = calibrateChlorophyll(lux);

    Serial.printf("[Chlorophyll] Lux: %.2f -> ppb: %.2f\n", lux, ppb);
    sendToThingSpeak(ppb, 0.0);
    logToSD(ppb, 0.0);

    digitalWrite(LED_CHLOROPHYLL, LOW);
    delay(1000);
}


void measureHumic() {
    digitalWrite(LED_HUMIC, HIGH);
    delay(500);

    float lux = readLux();
    float ppb = calibrateHumic(lux);

    Serial.printf("[Humic] Lux: %.2f -> ppb: %.2f\n", lux, ppb);
    sendToThingSpeak(0.0, ppb);
    logToSD(0.0, ppb);

    digitalWrite(LED_HUMIC, LOW);
    delay(1000);
}


void setup() {
    Serial.begin(115200);
    pinMode(LED_CHLOROPHYLL, OUTPUT);
    pinMode(LED_HUMIC, OUTPUT);

    // Connect to WiFi
    Serial.print("Connecting to WiFi");
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWiFi connected");

    
    if (!SD.begin(SD_CS_PIN)) {
        Serial.println("SD card initialization failed!");
    } else {
        Serial.println("SD card initialized successfully");
    }
}


void loop() {
    measureHumic();
    delay(2000); 
    measureChlorophyll();
    delay(2000);
  }
