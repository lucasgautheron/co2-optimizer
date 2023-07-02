#include <LiquidCrystal.h>

// LCD and buttons
const int btnsPin  = A0;
LiquidCrystal lcd(8, 9, 4, 5, 6, 7);;

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
      for(uint8_t i = 0; i < sizeof(charge_command); ++i) {
        uint8_t offset = i/4;
        val[i] += charge_command[i]; 
      }
      for (uint8_t i = 0; i < 12; ++i) {
        val[i] += 48;
      }
      val[12] = 0;
      lcd.print(val);
      break;
  }
}

void btnListener(byte btnStatus) { 
  switch (btnStatus) {
    case BUTTON_NONE:
      break;
    default:
      updateConfig(btnStatus);
      updateLCD();
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
}

void loop() {
  updateChargeState();
  btnListener(getBtnPressed());
  delay(100);
}