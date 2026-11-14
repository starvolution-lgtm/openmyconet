idf_component_register(SRCS "main.c" "bus.c" "uhr.c" "messung.c" "ablage.c" "akku.c"
                            "lora.c" "waechter.c"
                       INCLUDE_DIRS "."
                       REQUIRES omn_paket omn_treiber esp_app_format esp_driver_gpio
                                esp_driver_i2c esp_driver_spi esp_driver_sdspi fatfs sdmmc
                                nvs_flash esp_timer)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Wshadow -Werror)
