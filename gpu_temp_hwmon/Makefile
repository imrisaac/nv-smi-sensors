# Makefile for GPU temperature hwmon module

obj-m += gpu_temp_hwmon.o

KDIR := /lib/modules/$(shell uname -r)/build
PWD := $(shell pwd)

all:
	$(MAKE) -C $(KDIR) M=$(PWD) modules

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean

install: all
	sudo cp gpu_temp_hwmon.ko /lib/modules/$(shell uname -r)/kernel/drivers/hwmon/
	sudo depmod -a
	sudo modprobe gpu_temp_hwmon

uninstall:
	sudo modprobe -r gpu_temp_hwmon
	sudo rm -f /lib/modules/$(shell uname -r)/kernel/drivers/hwmon/gpu_temp_hwmon.ko
	sudo depmod -a

load:
	sudo insmod gpu_temp_hwmon.ko

unload:
	sudo rmmod gpu_temp_hwmon

.PHONY: all clean install uninstall load unload