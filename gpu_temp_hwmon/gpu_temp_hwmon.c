/*
 * gpu_temp_hwmon.c - Custom hwmon module for GPU temperature
 * Compile with: make -C /lib/modules/$(uname -r)/build M=$(pwd) modules
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/hwmon.h>
#include <linux/hwmon-sysfs.h>
#include <linux/platform_device.h>
#include <linux/fs.h>
#include <linux/uaccess.h>
#include <linux/slab.h>
#include <linux/err.h>

#define DRIVER_NAME "gpu_temp_hwmon"
#define TEMP_FILE "/tmp/gpu_max_temp"

MODULE_AUTHOR("AI Assistant");
MODULE_DESCRIPTION("GPU Temperature Hardware Monitor");
MODULE_LICENSE("GPL");
MODULE_VERSION("1.0");

static struct platform_device *pdev;
static struct device *hwmon_dev;

static ssize_t temp1_input_show(struct device *dev,
                               struct device_attribute *attr, char *buf)
{
    struct file *file;
    char temp_str[16];
    int temp_millidegrees = 0;
    loff_t pos = 0;
    int ret;

    // Read temperature from file
    file = filp_open(TEMP_FILE, O_RDONLY, 0);
    if (IS_ERR(file)) {
        return sprintf(buf, "0\n"); // Return 0 if file not found
    }

    ret = kernel_read(file, temp_str, sizeof(temp_str) - 1, &pos);
    if (ret > 0) {
        temp_str[ret] = '\0';
        ret = kstrtoint(temp_str, 10, &temp_millidegrees);
        if (ret < 0)
            temp_millidegrees = 0;
    }

    filp_close(file, NULL);
    return sprintf(buf, "%d\n", temp_millidegrees);
}

static ssize_t temp1_max_show(struct device *dev,
                             struct device_attribute *attr, char *buf)
{
    return sprintf(buf, "90000\n"); // 90°C max
}

static ssize_t temp1_crit_show(struct device *dev,
                              struct device_attribute *attr, char *buf)
{
    return sprintf(buf, "95000\n"); // 95°C critical
}

static SENSOR_DEVICE_ATTR(temp1_input, S_IRUGO, temp1_input_show, NULL, 0);
static SENSOR_DEVICE_ATTR(temp1_max, S_IRUGO, temp1_max_show, NULL, 0);
static SENSOR_DEVICE_ATTR(temp1_crit, S_IRUGO, temp1_crit_show, NULL, 0);

static struct attribute *gpu_temp_attrs[] = {
    &sensor_dev_attr_temp1_input.dev_attr.attr,
    &sensor_dev_attr_temp1_max.dev_attr.attr,
    &sensor_dev_attr_temp1_crit.dev_attr.attr,
    NULL
};

ATTRIBUTE_GROUPS(gpu_temp);

static int gpu_temp_probe(struct platform_device *pdev)
{
    hwmon_dev = devm_hwmon_device_register_with_groups(&pdev->dev,
                                                      "gpu_max_temp",
                                                      NULL,
                                                      gpu_temp_groups);
    return PTR_ERR_OR_ZERO(hwmon_dev);
}

static struct platform_driver gpu_temp_driver = {
    .driver = {
        .name = DRIVER_NAME,
    },
    .probe = gpu_temp_probe,
};

static int __init gpu_temp_init(void)
{
    int ret;

    ret = platform_driver_register(&gpu_temp_driver);
    if (ret)
        return ret;

    pdev = platform_device_register_simple(DRIVER_NAME, -1, NULL, 0);
    if (IS_ERR(pdev)) {
        platform_driver_unregister(&gpu_temp_driver);
        return PTR_ERR(pdev);
    }

    printk(KERN_INFO "GPU temperature hwmon module loaded\n");
    return 0;
}

static void __exit gpu_temp_exit(void)
{
    platform_device_unregister(pdev);
    platform_driver_unregister(&gpu_temp_driver);
    printk(KERN_INFO "GPU temperature hwmon module unloaded\n");
}

module_init(gpu_temp_init);
module_exit(gpu_temp_exit);

MODULE_ALIAS("platform:" DRIVER_NAME);