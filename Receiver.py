/*
 * ESP32 AQI Sensor Node - Transmitter
 * Real-Time Air Quality Monitoring System
 * 
 * Hardware:
 * - ESP32 Dev Kit
 * - DHT11 (Temperature & Humidity)
 * - PMS5003 (PM2.5 Sensor)
 * - MQ-135 (Gas Sensor)
 * - MQ-2 (Smoke Sensor)
 * - SX1276 LoRa Module
 * - SD Card Module
 * 
 * Author: [Your Name]
 * Date: 2025
 */

#include <SPI.h>
#include <LoRa.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <SD.h>

// ===== PIN DEFINITIONS =====
#define DHT_PIN 4
#define DHT_TYPE DHT11

// PMS5003 uses Serial2
#define PMS_RX 16
#define PMS_TX 17

// Analog sensors
#define GAS_SENSOR_PIN 36      // MQ-135
#define SMOKE_SENSOR_PIN 39    // MQ-2

// LoRa SPI pins
#define LORA_SCK 18
#define LORA_MISO 19
#define LORA_MOSI 23
#define LORA_SS 5
#define LORA_RST 14
#define LORA_DIO0 2

// SD Card SPI pins
#define SD_SCK 14
#define SD_MISO 12
#define SD_MOSI 13
#define SD_CS 15

// ===== CONFIGURATION =====
#define LORA_FREQUENCY 915E6    // 915 MHz (use 433E6 or 868E6 for other regions)
#define NODE_ID 1               // Unique ID for this sensor node
#define SENSOR_READ_INTERVAL 5000      // Read sensors every 5 seconds
#define LORA_TRANSMIT_INTERVAL 30000   // Transmit every 30 seconds
#define BAUD_RATE 115200

// ===== OBJECTS =====
DHT dht(DHT_PIN, DHT_TYPE);
HardwareSerial pmsSerial(2); // Use Serial2 for PMS5003

// ===== DATA STRUCTURE =====
struct SensorData {
  unsigned long timestamp;
  float temperature;
  float humidity;
  float pm25;
  float pm10;
  int gasLevel;
  int smokeLevel;
  int aqi;
};

SensorData currentData;
unsigned long lastSensorRead = 0;
unsigned long lastLoRaTransmit = 0;
unsigned long lastSDWrite = 0;
int packetCounter = 0;

// ===== SETUP =====
void setup() {
  Serial.begin(BAUD_RATE);
  delay(1000);
  
  Serial.println("=================================");
  Serial.println("AQI Sensor Node - Transmitter");
  Serial.println("=================================");
  
  // Initialize DHT11
  Serial.print("Initializing DHT11...");
  dht.begin();
  Serial.println("OK");
  
  // Initialize PMS5003
  Serial.print("Initializing PMS5003...");
  pmsSerial.begin(9600, SERIAL_8N1, PMS_RX, PMS_TX);
  Serial.println("OK");
  
  // Initialize SD Card
  Serial.print("Initializing SD Card...");
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS)) {
    Serial.println("FAILED!");
    Serial.println("Warning: SD Card not available. Data will not be logged.");
  } else {
    Serial.println("OK");
    createCSVHeader();
  }
  
  // Initialize LoRa
  Serial.print("Initializing LoRa...");
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  
  if (!LoRa.begin(LORA_FREQUENCY)) {
    Serial.println("FAILED!");
    Serial.println("ERROR: LoRa initialization failed. Check wiring!");
    while (1); // Halt execution
  }
  
  // Configure LoRa parameters for long range
  LoRa.setSpreadingFactor(12);        // SF12 for maximum range
  LoRa.setSignalBandwidth(125E3);     // 125 kHz bandwidth
  LoRa.setCodingRate4(5);             // 4/5 coding rate
  LoRa.setTxPower(20);                // 20 dBm (max power)
  LoRa.enableCrc();                   // Enable CRC
  
  Serial.println("OK");
  Serial.print("LoRa Frequency: ");
  Serial.print(LORA_FREQUENCY / 1E6);
  Serial.println(" MHz");
  
  Serial.println("=================================");
  Serial.println("System Ready!");
  Serial.println("=================================\n");
  
  delay(2000);
}

// ===== MAIN LOOP =====
void loop() {
  unsigned long currentMillis = millis();
  
  // Read sensors at defined interval
  if (currentMillis - lastSensorRead >= SENSOR_READ_INTERVAL) {
    readAllSensors();
    calculateAQI();
    displayReadings();
    
    // Write to SD card every 10 seconds
    if (currentMillis - lastSDWrite >= 10000) {
      writeToSDCard();
      lastSDWrite = currentMillis;
    }
    
    lastSensorRead = currentMillis;
  }
  
  // Transmit via LoRa at defined interval
  if (currentMillis - lastLoRaTransmit >= LORA_TRANSMIT_INTERVAL) {
    transmitData();
    lastLoRaTransmit = currentMillis;
  }
  
  delay(100); // Small delay to prevent WDT reset
}

// ===== READ ALL SENSORS =====
void readAllSensors() {
  // Read DHT11
  currentData.temperature = dht.readTemperature();
  currentData.humidity = dht.readHumidity();
  
  // Check if DHT reading failed
  if (isnan(currentData.temperature) || isnan(currentData.humidity)) {
    Serial.println("Warning: DHT11 reading failed!");
    currentData.temperature = 0;
    currentData.humidity = 0;
  }
  
  // Read PMS5003
  readPMS5003();
  
  // Read analog gas sensors
  currentData.gasLevel = analogRead(GAS_SENSOR_PIN);
  currentData.smokeLevel = analogRead(SMOKE_SENSOR_PIN);
  
  // Get timestamp
  currentData.timestamp = millis() / 1000; // Convert to seconds
}

// ===== READ PMS5003 SENSOR =====
void readPMS5003() {
  if (pmsSerial.available() >= 32) {
    uint8_t buffer[32];
    int index = 0;
    bool frameFound = false;
    
    // Look for start bytes 0x42 0x4d
    while (pmsSerial.available() > 0) {
      uint8_t byte1 = pmsSerial.read();
      if (byte1 == 0x42) {
        uint8_t byte2 = pmsSerial.read();
        if (byte2 == 0x4d) {
          buffer[0] = byte1;
          buffer[1] = byte2;
          frameFound = true;
          break;
        }
      }
    }
    
    if (frameFound) {
      // Read rest of frame
      for (int i = 2; i < 32; i++) {
        if (pmsSerial.available() > 0) {
          buffer[i] = pmsSerial.read();
        } else {
          break;
        }
      }
      
      // Extract PM2.5 and PM10 (atmospheric environment)
      currentData.pm25 = (buffer[12] << 8) | buffer[13];
      currentData.pm10 = (buffer[14] << 8) | buffer[15];
    }
  } else {
    // No data available, use previous values or set to 0
    static bool firstRead = true;
    if (firstRead) {
      currentData.pm25 = 0;
      currentData.pm10 = 0;
      firstRead = false;
    }
  }
}

// ===== CALCULATE AQI =====
void calculateAQI() {
  // Calculate AQI based on PM2.5 (primary pollutant)
  float pm25 = currentData.pm25;
  int pm25_aqi = 0;
  
  // EPA AQI breakpoints for PM2.5
  if (pm25 <= 12.0) {
    pm25_aqi = map(pm25 * 10, 0, 120, 0, 50);
  } else if (pm25 <= 35.4) {
    pm25_aqi = map(pm25 * 10, 121, 354, 51, 100);
  } else if (pm25 <= 55.4) {
    pm25_aqi = map(pm25 * 10, 355, 554, 101, 150);
  } else if (pm25 <= 150.4) {
    pm25_aqi = map(pm25 * 10, 555, 1504, 151, 200);
  } else if (pm25 <= 250.4) {
    pm25_aqi = map(pm25 * 10, 1505, 2504, 201, 300);
  } else {
    pm25_aqi = map(pm25 * 10, 2505, 5000, 301, 500);
    if (pm25_aqi > 500) pm25_aqi = 500;
  }
  
  // Calculate PM10 AQI
  float pm10 = currentData.pm10;
  int pm10_aqi = 0;
  
  if (pm10 <= 54) {
    pm10_aqi = map(pm10, 0, 54, 0, 50);
  } else if (pm10 <= 154) {
    pm10_aqi = map(pm10, 55, 154, 51, 100);
  } else if (pm10 <= 254) {
    pm10_aqi = map(pm10, 155, 254, 101, 150);
  } else if (pm10 <= 354) {
    pm10_aqi = map(pm10, 255, 354, 151, 200);
  } else if (pm10 <= 424) {
    pm10_aqi = map(pm10, 355, 424, 201, 300);
  } else {
    pm10_aqi = map(pm10, 425, 604, 301, 500);
    if (pm10_aqi > 500) pm10_aqi = 500;
  }
  
  // Environmental correction factors
  float tempFactor = 1.0;
  float humidityFactor = 1.0;
  
  if (currentData.temperature > 35) {
    tempFactor = 1.1; // 10% increase for extreme heat
  } else if (currentData.temperature < 0) {
    tempFactor = 1.05; // 5% increase for freezing
  }
  
  if (currentData.humidity > 80) {
    humidityFactor = 1.05; // 5% increase for high humidity
  }
  
  // Gas sensor contribution (normalized to 0-50 range)
  float gasFactor = map(currentData.gasLevel, 0, 4095, 0, 50);
  float smokeFactor = map(currentData.smokeLevel, 0, 4095, 0, 50);
  
  // Composite AQI calculation with weighting
  float compositeAQI = (pm25_aqi * 0.4) + 
                       (pm10_aqi * 0.3) + 
                       (gasFactor * 0.15) + 
                       (smokeFactor * 0.05);
  
  // Apply environmental corrections
  compositeAQI = compositeAQI * tempFactor * humidityFactor;
  
  // Environmental stress bonus
  float envStress = (abs(currentData.temperature - 25) + abs(currentData.humidity - 50)) / 100.0;
  compositeAQI += (envStress * 10);
  
  // Bounds checking
  if (compositeAQI > 500) compositeAQI = 500;
  if (compositeAQI < 0) compositeAQI = 0;
  
  currentData.aqi = (int)compositeAQI;
}

// ===== DISPLAY READINGS =====
void displayReadings() {
  Serial.println("\n======= SENSOR READINGS =======");
  Serial.print("Timestamp: ");
  Serial.print(currentData.timestamp);
  Serial.println(" seconds");
  
  Serial.print("Temperature: ");
  Serial.print(currentData.temperature);
  Serial.println(" °C");
  
  Serial.print("Humidity: ");
  Serial.print(currentData.humidity);
  Serial.println(" %");
  
  Serial.print("PM2.5: ");
  Serial.print(currentData.pm25);
  Serial.println(" µg/m³");
  
  Serial.print("PM10: ");
  Serial.print(currentData.pm10);
  Serial.println(" µg/m³");
  
  Serial.print("Gas Level: ");
  Serial.print(currentData.gasLevel);
  Serial.println(" (0-4095)");
  
  Serial.print("Smoke Level: ");
  Serial.print(currentData.smokeLevel);
  Serial.println(" (0-4095)");
  
  Serial.print("AQI: ");
  Serial.print(currentData.aqi);
  Serial.print(" (");
  Serial.print(getAQICategory(currentData.aqi));
  Serial.println(")");
  
  Serial.println("===============================\n");
}

// ===== TRANSMIT DATA VIA LORA =====
void transmitData() {
  Serial.println(">>> Transmitting data via LoRa...");
  
  // Create JSON document
  StaticJsonDocument<256> doc;
  
  doc["node_id"] = NODE_ID;
  doc["packet"] = packetCounter++;
  doc["timestamp"] = currentData.timestamp;
  doc["temp"] = round(currentData.temperature * 10) / 10.0;
  doc["humidity"] = round(currentData.humidity * 10) / 10.0;
  doc["pm25"] = round(currentData.pm25 * 10) / 10.0;
  doc["pm10"] = round(currentData.pm10 * 10) / 10.0;
  doc["gas"] = currentData.gasLevel;
  doc["smoke"] = currentData.smokeLevel;
  doc["aqi"] = currentData.aqi;
  
  // Serialize to string
  String jsonString;
  serializeJson(doc, jsonString);
  
  Serial.print("JSON: ");
  Serial.println(jsonString);
  
  // Send via LoRa
  LoRa.beginPacket();
  LoRa.print(jsonString);
  LoRa.endPacket();
  
  Serial.print("✓ Packet #");
  Serial.print(packetCounter);
  Serial.println(" transmitted successfully!");
  Serial.print("Size: ");
  Serial.print(jsonString.length());
  Serial.println(" bytes\n");
}

// ===== SD CARD FUNCTIONS =====
void createCSVHeader() {
  if (!SD.exists("/aqi_data.csv")) {
    File dataFile = SD.open("/aqi_data.csv", FILE_WRITE);
    if (dataFile) {
      dataFile.println("timestamp,node_id,temperature,humidity,pm25,pm10,gas,smoke,aqi");
      dataFile.close();
      Serial.println("CSV header created on SD card");
    } else {
      Serial.println("Error creating CSV file");
    }
  }
}

void writeToSDCard() {
  File dataFile = SD.open("/aqi_data.csv", FILE_APPEND);
  
  if (dataFile) {
    dataFile.print(currentData.timestamp);
    dataFile.print(",");
    dataFile.print(NODE_ID);
    dataFile.print(",");
    dataFile.print(currentData.temperature);
    dataFile.print(",");
    dataFile.print(currentData.humidity);
    dataFile.print(",");
    dataFile.print(currentData.pm25);
    dataFile.print(",");
    dataFile.print(currentData.pm10);
    dataFile.print(",");
    dataFile.print(currentData.gasLevel);
    dataFile.print(",");
    dataFile.print(currentData.smokeLevel);
    dataFile.print(",");
    dataFile.println(currentData.aqi);
    
    dataFile.close();
    Serial.println("✓ Data written to SD card");
  } else {
    Serial.println("✗ Error writing to SD card");
  }
}

// ===== UTILITY FUNCTIONS =====
String getAQICategory(int aqi) {
  if (aqi <= 50) return "Good";
  else if (aqi <= 100) return "Moderate";
  else if (aqi <= 150) return "Unhealthy for Sensitive";
  else if (aqi <= 200) return "Unhealthy";
  else if (aqi <= 300) return "Very Unhealthy";
  else return "Hazardous";
}

// ===== ERROR HANDLING =====
void handleError(String errorMsg) {
  Serial.print("ERROR: ");
  Serial.println(errorMsg);
  
  // Optionally: Send error via LoRa
  LoRa.beginPacket();
  LoRa.print("{\"error\":\"");
  LoRa.print(errorMsg);
  LoRa.print("\"}");
  LoRa.endPacket();
}
