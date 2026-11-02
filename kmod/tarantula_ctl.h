/* SPDX-License-Identifier: GPL-2.0-only WITH Linux-syscall-note */
#ifndef TARANTULA_CTL_H
#define TARANTULA_CTL_H

#include <linux/ioctl.h>
#include <linux/types.h>

#define TAR_DIR_SET 0
#define TAR_DIR_GET 1
#define TAR_MAX_LEN 472

struct tarantula_xfer {
	__u8 dir;          /* TAR_DIR_SET / TAR_DIR_GET */
	__u8 report_id;    /* 1..8 */
	__u8 report_type;  /* wValue high byte; Windows driver uses 0 */
	__u8 flags;        /* must be 0 */
	__u16 windex;      /* 0 for commands, profile 1..5 for settings */
	__u16 len;         /* 1..472 */
	__u64 data;        /* user buffer */
};

#define TARANTULA_IOC_XFER _IOWR('T', 0x01, struct tarantula_xfer)

#endif
