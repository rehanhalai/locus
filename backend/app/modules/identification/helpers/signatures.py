"""Known binary magic bytes and signature definitions for forensic device and filesystem identification."""

# MBR and GPT partition table signatures
MBR_BOOT_SIGNATURE = b"\x55\xaa"  # Offset 510-511 in Sector 0 (LBA 0)
MBR_PARTITION_TABLE_OFFSET = 446  # 0x01BE
MBR_PARTITION_ENTRY_SIZE = 16  # 16 bytes per partition record
MBR_MAX_PRIMARY_PARTITIONS = 4
GPT_PROTECTIVE_TYPE = 0xEE  # Partition type byte indicating GPT

GPT_HEADER_SIGNATURE = b"EFI PART"  # Offset 0 in Sector 1 (LBA 1)

# Standalone Media Container Signatures
MP4_FTYP_MAGIC = b"ftyp"  # Offset 4 in MP4 container files
AVI_RIFF_MAGIC = b"RIFF"  # Offset 0 in AVI container files
DAHUA_DHAV_MAGIC = b"DHAV"  # Offset 0 in Dahua .dav files & video frames
DAHUA_DHAV_FOOTER = b"dhav"  # End of frame magic

# Filesystem Superblock Signatures (Checked at Sector 0 / 2048 of partition)
DAHUA_DHFS_MAGIC = b"DHFS"  # Offset 0: Dahua File System (DHFS 4.1)
HIKVISION_HKFS_MAGIC = b"HKFS"  # Offset 0: Hikvision File System
HIKVISION_HIKB_MAGIC = b"HIKB"  # Offset 0: Hikvision Block Header
HIKVISION_BTREE_MAGIC = b"HIKBTREE"  # Master Index B+ Tree
WFS_MAGIC_NULL = b"WFS\x00"  # Offset 0: Swann / Asian OEM WFS
WFS_MAGIC_VERSION = b"WFS 0.4"  # Offset 0: WFS version string

# Standard Filesystems
FAT32_MAGIC = b"FAT32   "  # Offset 82 in FAT32 boot sector
FAT_OEM_MAGIC = b"MSDOS5.0"  # Offset 3 in FAT boot sector
EXFAT_MAGIC = b"EXFAT   "  # Offset 3 in exFAT boot sector
NTFS_MAGIC = b"NTFS    "  # Offset 3 in NTFS boot sector
EXT4_SUPERBLOCK_OFFSET = 1080  # 1024 + 56 in ext4 partition
EXT4_MAGIC = b"\x53\xef"  # ext4 magic number (0xEF53 little endian)

# Raw Video NAL Unit Start Codes (H.264 / H.265)
H264_START_CODE_4 = b"\x00\x00\x00\x01"
H264_START_CODE_3 = b"\x00\x00\x01"

# H.264 NAL Unit Types (nal_unit_type = byte & 0x1F)
H264_NAL_SPS = 7  # Sequence Parameter Set (0x67)
H264_NAL_PPS = 8  # Picture Parameter Set (0x68)
H264_NAL_IDR = 5  # Keyframe / I-Frame (0x65)
H264_NAL_NON_IDR = 1  # P-Frame (0x41 or 0x61)

# H.265 (HEVC) NAL Unit Types (nal_unit_type = (byte & 0x7E) >> 1)
H265_NAL_VPS = 32  # Video Parameter Set (0x40)
H265_NAL_SPS = 33  # Sequence Parameter Set (0x42)
H265_NAL_PPS = 34  # Picture Parameter Set (0x44)
H265_NAL_IDR_W_RADL = 19  # Keyframe (0x26)
H265_NAL_IDR_N_LP = 20  # Keyframe (0x28)
H265_NAL_CRA = 21  # Clean Random Access Keyframe (0x2A)
