#include <LiquidCrystal.h>

#include "WiFiS3.h"

char ssid[] = "SSID";        // your network SSID (name)
char pass[] = "12345678";    // your network password (use for WPA, or use as key for WEP)
int keyIndex = 0;            // your network key index number (needed only for WEP)

int status = WL_IDLE_STATUS;
WiFiClient client;
char server[] = "192.168.0.1";
bool awaiting_http_response = false;
unsigned long last_request = 0;

// LCD and buttons
const int btnsPin  = A0;
LiquidCrystal lcd(8, 9, 4, 5, 6, 7);;
bool update_lcd = true;

enum {
  BUTTON_NONE,
  BUTTON_UP,
  BUTTON_DOWN,
  BUTTON_LEFT,
  BUTTON_RIGHT,
  BUTTON_SELECT,
};

// menus
enum {
  CONFIG_MENU_NONE,
  CONFIG_MENU_CHARGE_TIME,
  CONFIG_MENU_MAX_TIME,
  CONFIG_MENU_FORCED_CHARGE,
  CONFIG_CHARGE_PROFILE,

};

uint8_t current_config_menu = CONFIG_MENU_NONE;
uint8_t config_charge_time = 0;
uint8_t config_max_time = 0;
uint8_t config_force = 0;

// charge management
unsigned long charge_start_time = 0;
uint8_t current_charge_hour = 0;
uint8_t charge_command[48];

void printWifiStatus() {
/* -------------------------------------------------------------------------- */  
  // print the SSID of the network you're attached to:
  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());

  // print your board's IP address:
  IPAddress ip = WiFi.localIP();
  Serial.print("IP Address: ");
  Serial.println(ip);

  // print the received signal strength:
  long rssi = WiFi.RSSI();
  Serial.print("signal strength (RSSI):");
  Serial.print(rssi);
  Serial.println(" dBm");
}

void setup_wifi() {
  Serial.begin(9600);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }

  // check for the WiFi module:
  if (WiFi.status() == WL_NO_MODULE) {
    Serial.println("Communication with WiFi module failed!");
    while (true);
  }

  String fv = WiFi.firmwareVersion();
  if (fv < WIFI_FIRMWARE_LATEST_VERSION) {
    Serial.println("Please upgrade the firmware");
  }

  while (status != WL_CONNECTED) {
    Serial.print("Attempting to connect to SSID: ");
    Serial.println(ssid);
    // Connect to WPA/WPA2 network. Change this line if using open or WEP network:
    status = WiFi.begin(ssid, pass);

    // wait 10 seconds for connection:
    //delay(10000);
  }
  // you're connected now, so print out the status:
  printWifiStatus();
}

void readCommand() {
  for(uint8_t i = 0; i < sizeof(charge_command); ++i)
    charge_command[i] = i;

  uint32_t received_data_num = 0;
  bool body = false;

  while (client.available()) {
    char c = client.read();
    Serial.print(c);

    if (!body) {
      if (c == '\n') {
        body = true;
      }
      continue;
    }
    
    charge_command[received_data_num] = c-'0';

    received_data_num++;
    if(received_data_num % sizeof(charge_command) == 0) { 
      break;
    }
  }
  if (received_data_num>0) {
    awaiting_http_response = false;
    update_lcd = true;
    return;
  }

  if (millis()-last_request>60L * 1000L) {
    awaiting_http_response = false;
  }
}


void httpQueryCommand() {
/* -------------------------------------------------------------------------- */  
  // close any connection before send a new request.
  // This will free the socket on the NINA module
  client.stop();

  if (client.connect(server, 80)) {
    Serial.println("connecting...");
    char get[64];
    sprintf(get, "GET /command/time=%d&max_time=&d HTTP/1.1", config_charge_time, config_max_time);
    client.println(get);
    client.println("Host: 192.168.0.1");
    client.println("User-Agent: ArduinoWiFi/1.1");
    client.println("Connection: close");
    client.println();

    last_request = millis();
    awaiting_http_response = true;
  } else {
    // if you couldn't make a connection:
    Serial.println("connection failed");
  }
}

bool updateChargeState() {
  // forced mode is on
  if (config_force) {
    return true;
  }

  // force mode off and no charge time left
  if (config_charge_time == 0) {
    return false;
  }

  uint8_t hour = (millis()-charge_start_time)/3600000;

  // an hour of charge has just elasped
  if (hour > current_charge_hour) {
    current_charge_hour = hour;
    config_charge_time--;

    if (config_charge_time < 0) {
      config_charge_time = 0;
      return false;
    }
  }
  
  if (hour>48) {
    return false;
  }

  return charge_command[hour];
}

void updateConfig(byte btnStatus) {
  // navigate menus
  switch(btnStatus) {
    case BUTTON_LEFT:
      current_config_menu--;
      return;
    case BUTTON_RIGHT:
      current_config_menu++;
      return;
    case BUTTON_SELECT:
      current_config_menu = CONFIG_MENU_NONE;
      return;
    default:
      break;
  }

  // update configuration
  switch (current_config_menu) {
    case CONFIG_MENU_CHARGE_TIME:
      if (btnStatus == BUTTON_UP) {
        config_charge_time++;
      }
      else if (btnStatus == BUTTON_DOWN) {
        config_charge_time--;
      }

      if (config_charge_time > 48) {
        config_charge_time = 48;
      }
      else if (config_charge_time<0) {
        config_charge_time = 0;
      }
      httpQueryCommand();
      charge_start_time = millis();
      break;

    case CONFIG_MENU_MAX_TIME:
      if (btnStatus == BUTTON_UP) {
        config_max_time++;
      }
      else if (btnStatus == BUTTON_DOWN) {
        config_max_time--;
      }

      if (config_charge_time > 48) {
        config_max_time = 48;
      }
      else if (config_charge_time<0) {
        config_max_time = 0;
      }
      httpQueryCommand();
      break;

    case CONFIG_MENU_FORCED_CHARGE:
      config_force = 1-config_force;
      break;

    default://case BUTTON_NONE:
      //lcd.print(F("       "));
      break;
  }
}

void updateLCD() {
  char val[16];

  switch (current_config_menu) {
    case CONFIG_MENU_NONE:
      break;
    case CONFIG_MENU_CHARGE_TIME:
      lcd.setCursor(0, 0);
      lcd.print(F("Charge time:"));

      lcd.setCursor(0, 1);
      sprintf(val, "%d hours", config_max_time);
      lcd.print(val);

      break;
    case CONFIG_MENU_MAX_TIME:
      lcd.setCursor(0, 0);
      lcd.print(F("Max duration:"));

      lcd.setCursor(0, 1);
      sprintf(val, "%d hours", config_max_time);
      lcd.print(val);
      break;

    case CONFIG_MENU_FORCED_CHARGE:
      lcd.setCursor(0, 0);
      if (config_force == 0) {
        lcd.print(F("Forced mode off"));
      }
      else {
        lcd.print(F("Forced mode on"));
      }
      break;

    case CONFIG_CHARGE_PROFILE:
      lcd.setCursor(0, 0);
      lcd.print(F("0h       48h"));

      lcd.setCursor(0, 1);
      for (uint8_t i = 0; i < 12; ++i) {
        val[i] = '0';
      }

      for(uint8_t i = 0; i < sizeof(charge_command); ++i) {
        uint8_t offset = i/4;
        val[i] += charge_command[i]; 
      }
      
      val[12] = 0;
      lcd.print(val);
      break;
  }
  update_lcd = false;
}

void btnListener(byte btnStatus) { 
  switch (btnStatus) {
    case BUTTON_NONE:
      break;
    default:
      updateConfig(btnStatus);
      update_lcd = true;
  }
}

byte getBtnPressed() {
  int btnsVal = analogRead(btnsPin);
  if (btnsVal < 50)
    return BUTTON_RIGHT;
  else if (btnsVal < 250)
    return BUTTON_UP;
  else if (btnsVal < 350)
    return BUTTON_DOWN;
  else if (btnsVal < 450)
    return BUTTON_LEFT;
  else if (btnsVal < 650)
    return BUTTON_SELECT;
  else
    return BUTTON_NONE;
}


void setup_lcd() {
  Serial.begin(9600);
  Serial.println(F("Initialize System"));
  //Init LCD16x2 Shield
  lcd.begin(16, 2);
}



void setup() {
  for(uint8_t i = 0; i < sizeof(charge_command); ++i)
    charge_command[i] = i;

  setup_lcd();
  setup_wifi();
}

void loop() {
  if (awaiting_http_response) {
    readCommand();
  }

  updateChargeState();
  
  btnListener(getBtnPressed());

  if (update_lcd) {
    updateLCD();
  }

  delay(100);
}