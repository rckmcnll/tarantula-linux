// SPDX-License-Identifier: GPL-2.0-only
/*
 * tarantula_ctl - profile access for the Razer Tarantula keyboard (USB 1532:0102)
 *
 * The keyboard selects its on-board profile (1..5) through the wIndex field of
 * HID class GET/SET_REPORT requests. usbfs/hidraw only let user space put a
 * real interface number (0 or 1) there, so this module issues those requests
 * from the kernel. It does NOT bind to the device; usbhid keeps the keyboard.
 *
 * /dev/tarantula, ioctl TARANTULA_IOC_XFER. Requests are restricted to the
 * Tarantula's own protocol: HID class report requests to interface recipient,
 * report id 1..8, wIndex 0..5, length 1..472.
 */
#include <linux/module.h>
#include <linux/miscdevice.h>
#include <linux/mutex.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/usb.h>
#include "tarantula_ctl.h"

#define TAR_VID 0x1532
#define TAR_PID 0x0102
#define HID_REQ_GET_REPORT 0x01
#define HID_REQ_SET_REPORT 0x09
#define TAR_TIMEOUT_MS 1000

static DEFINE_MUTEX(tar_lock);

static int tar_match(struct usb_device *udev, void *data)
{
	struct usb_device **found = data;

	if (le16_to_cpu(udev->descriptor.idVendor) == TAR_VID &&
	    le16_to_cpu(udev->descriptor.idProduct) == TAR_PID) {
		*found = usb_get_dev(udev);
		return 1;
	}
	return 0;
}

static long tar_xfer(struct tarantula_xfer __user *uarg)
{
	struct tarantula_xfer x;
	struct usb_device *udev = NULL;
	void __user *ubuf;
	u8 *buf;
	int ret;

	if (copy_from_user(&x, uarg, sizeof(x)))
		return -EFAULT;
	if (x.dir > TAR_DIR_GET || x.report_id < 1 || x.report_id > 8 ||
	    x.report_type > 3 || x.windex > 5 || x.len < 1 ||
	    x.len > TAR_MAX_LEN || x.flags)
		return -EINVAL;
	ubuf = u64_to_user_ptr(x.data);

	buf = kzalloc(x.len, GFP_KERNEL);
	if (!buf)
		return -ENOMEM;
	if (x.dir == TAR_DIR_SET && copy_from_user(buf, ubuf, x.len)) {
		ret = -EFAULT;
		goto out_free;
	}

	mutex_lock(&tar_lock);
	usb_for_each_dev(&udev, tar_match);
	if (!udev) {
		ret = -ENODEV;
		goto out_unlock;
	}
	if (x.dir == TAR_DIR_GET)
		ret = usb_control_msg(udev, usb_rcvctrlpipe(udev, 0),
				      HID_REQ_GET_REPORT,
				      USB_DIR_IN | USB_TYPE_CLASS | USB_RECIP_INTERFACE,
				      (x.report_type << 8) | x.report_id, x.windex,
				      buf, x.len, TAR_TIMEOUT_MS);
	else
		ret = usb_control_msg(udev, usb_sndctrlpipe(udev, 0),
				      HID_REQ_SET_REPORT,
				      USB_DIR_OUT | USB_TYPE_CLASS | USB_RECIP_INTERFACE,
				      (x.report_type << 8) | x.report_id, x.windex,
				      buf, x.len, TAR_TIMEOUT_MS);
	usb_put_dev(udev);
out_unlock:
	mutex_unlock(&tar_lock);
	if (ret > 0 && x.dir == TAR_DIR_GET && copy_to_user(ubuf, buf, ret))
		ret = -EFAULT;
out_free:
	kfree(buf);
	return ret;
}

static long tar_ioctl(struct file *f, unsigned int cmd, unsigned long arg)
{
	if (cmd == TARANTULA_IOC_XFER)
		return tar_xfer((struct tarantula_xfer __user *)arg);
	return -ENOTTY;
}

static const struct file_operations tar_fops = {
	.owner = THIS_MODULE,
	.unlocked_ioctl = tar_ioctl,
	.compat_ioctl = compat_ptr_ioctl,
};

static struct miscdevice tar_misc = {
	.minor = MISC_DYNAMIC_MINOR,
	.name = "tarantula",
	.fops = &tar_fops,
	.mode = 0600,
};

module_misc_device(tar_misc);

MODULE_DESCRIPTION("Razer Tarantula on-board profile access (HID report requests with profile wIndex)");
MODULE_AUTHOR("tarantula-re");
MODULE_LICENSE("GPL");
