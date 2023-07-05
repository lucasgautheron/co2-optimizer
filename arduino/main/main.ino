#include <LiquidCrystal.h>

#include "WiFiS3.h"

char ssid[] = "gautheron";   // your network SSID (name)
char pass[] = "12345678";    // your network password (use for WPA, or use as key for WEP)
int keyIndex = 0;            // your network key index number (needed only for WEP)

int status = WL_IDLE_STATUS;
WiFiClient client;
char server[] = "15.237.56.158";
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
  CONFIG_MENU_LAST,
};

uint8_t current_config_menu = CONFIG_MENU_NONE;
uint8_t config_charge_time = 0;
uint8_t config_max_time = 0;
uint8_t config_force = 0;

// charge management
enum {
  CHARGE_INACTIVE,
  CHARGE_ACTIVE,
  CHARGE_PENDING,
  CHARGE_DONE
};

const unsigned long HOUR = 10L * 1000L;
unsigned long charge_start_time = 0;
uint8_t current_charge_hour = 0;
uint8_t charge_command[48];
uint8_t charge_state = CHARGE_INACTIVE;
uint8_t prev_charge_state = CHARGE_INACTIVE;

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
    lcd.clear();
    lcd.setCursor(0,0);
    lcd.print(F("wifi unavailable"));
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
    lcd.clear();
    lcd.setCursor(0,0);
    lcd.print(F("connecting..."));
    // wait 10 seconds for connection:
    //delay(10000);
  }

  // you're connected now, so print out the status:
  printWifiStatus();
}

void readCommand() {
  for(uint8_t i = 0; i < sizeof(charge_command); ++i)
    charge_command[i] = 0;

  uint32_t received_data_num = 0;
  bool body = false;

  char buf[4];
  for(uint8_t i = 0; i < sizeof(buf); ++i) {
    buf[i] = 0;
  }

  while (client.available()) {
    char c = client.read();
    Serial.print(c);

    for(uint8_t i = 0; i < sizeof(buf)-1; ++i) {
      buf[i] = buf[i+1];
    }
    buf[sizeof(buf)-1] = c;

    if (!body) {
      if (buf[0] == 13 && buf[1] == 10 && buf[2] == 13 && buf[3] == 10) {
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
    sprintf(get, "GET /command/?time=%d&max_time=%d HTTP/1.1", config_charge_time, config_max_time);
    client.println(get);
    client.println("Host: 15.237.56.158");
    client.println("User-Agent: ArduinoWiFi/1.1");
    client.println("Connection: close");
    client.println();
    last_request = millis();
    awaiting_http_response = true;
    delay(2000);
  } else {
    // if you couldn't make a connection:
    Serial.println("connection failed");
  }
}

void updateChargeState() {
  // forced mode is on
  if (config_force) {
    charge_state = CHARGE_ACTIVE;
    return;
  }

  // force mode off and no charge time left
  if (config_charge_time == 0) {
    charge_state = CHARGE_DONE;
    return;
  }

  uint8_t current_hour = (millis()-charge_start_time)/HOUR;

  // an hour has just elasped
  if (current_hour > current_charge_hour) {
    current_charge_hour = current_hour;
    update_lcd = true;
    
    // if we have been charging, decrease remaning charge time
    if (charge_command[current_charge_hour] > 0) {

      if (config_charge_time == 1) {
        config_charge_time = 0;
        charge_state = CHARGE_DONE;
        return;
      }
      else {
        config_charge_time--;
        config_max_time--;
      }
    }
  }
  
  if (current_hour>48) {
    charge_state = CHARGE_DONE;
    return;
  }

  if(charge_command[current_hour] == 0) {
    charge_state = CHARGE_PENDING;
  }
  else {
    charge_state = CHARGE_ACTIVE;
  }
}

void updateConfig(byte btnStatus) {
  // navigate menus
  switch(btnStatus) {
    case BUTTON_LEFT:
      current_config_menu--;
      if (current_config_menu >= CONFIG_MENU_LAST) {
        current_config_menu = CONFIG_MENU_NONE;
      }
      break;
    case BUTTON_RIGHT:
      current_config_menu++;
      if (current_config_menu >= CONFIG_MENU_LAST) {
        current_config_menu = CONFIG_MENU_NONE;
      }
      break;
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
      else if(btnStatus == BUTTON_SELECT) {
        httpQueryCommand();
        charge_start_time = millis();
        current_charge_hour = 0;
      }

      if (config_charge_time > 48) {
        config_charge_time = 48;
      }
      else if (config_charge_time<0) {
        config_charge_time = 0;
      }
      break;

    case CONFIG_MENU_MAX_TIME:
      if (btnStatus == BUTTON_UP) {
        config_max_time++;
      }
      else if (btnStatus == BUTTON_DOWN) {
        config_max_time--;
      }
      else if(btnStatus == BUTTON_SELECT) {
        httpQueryCommand();
        charge_start_time = millis();
        current_charge_hour = 0;
      }

      if (config_charge_time > 48) {
        config_max_time = 48;
      }
      else if (config_charge_time<0) {
        config_max_time = 0;
      }
      break;

    case CONFIG_MENU_FORCED_CHARGE:
      if (btnStatus == BUTTON_UP || btnStatus == BUTTON_DOWN) {
        config_force = 1-config_force;
      }
      break;

    default://case BUTTON_NONE:
      //lcd.print(F("       "));
      break;
  }
}

void updateLCD() {
  char buf[16];

  lcd.clear();
  switch (current_config_menu) {
    case CONFIG_MENU_NONE: {
      lcd.setCursor(0,0);
      if (charge_state == CHARGE_INACTIVE) {
        lcd.print(F("charge: inactive"));
      }
      else if (charge_state == CHARGE_ACTIVE) {
        lcd.print(F("charge: active"));
      }
      else if (charge_state == CHARGE_PENDING) {
        lcd.print(F("charge: pending"));
      }
      else if (charge_state == CHARGE_DONE) {
        lcd.print(F("charge: done"));
      }
      
      if (config_force || (charge_state != CHARGE_PENDING && charge_state != CHARGE_ACTIVE))
        break;
      
      lcd.setCursor(0,1);
      int8_t i = sizeof(charge_command)-1;
      for (; i >= 0; i--) {
        if(charge_command[i] == 1) {
          break;
        }
      }
      sprintf(buf, "%d hours left", i-current_charge_hour+1);
      lcd.print(buf);
      break;
    }
    case CONFIG_MENU_CHARGE_TIME:
      lcd.setCursor(0, 0);
      lcd.print(F("Charge time:"));

      lcd.setCursor(0, 1);
      sprintf(buf, "%d hours", config_charge_time);
      lcd.print(buf);

      break;
    case CONFIG_MENU_MAX_TIME:
      lcd.setCursor(0, 0);
      lcd.print(F("Max duration:"));

      lcd.setCursor(0, 1);
      sprintf(buf, "%d hours", config_max_time);
      lcd.print(buf);
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

      for (uint8_t i = 0; i < 12; ++i) {
        buf[i] = '0';
      }

      for(uint8_t i = 0; i < sizeof(charge_command); ++i) {
        uint8_t offset = i/4;
        buf[offset] += charge_command[i];
      }
      
      buf[12] = 0;
      lcd.setCursor(0, 1);
      lcd.print(buf);
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
  lcd.print(F("restarting"));
  delay(1000);
}



void setup() {
  for(uint8_t i = 0; i < sizeof(charge_command); ++i)
    charge_command[i] = 0;

  setup_lcd();
  setup_wifi();
}

void loop() {
  if (awaiting_http_response) {
    readCommand();
  }

  updateChargeState();

  if (prev_charge_state != charge_state) {
    prev_charge_state = charge_state;
    update_lcd = true;
  }
  
  btnListener(getBtnPressed());

  if (update_lcd) {
    updateLCD();
  }

  delay(100);
}