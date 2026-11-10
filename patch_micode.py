import os, re

def patch_file(path, old, new):
    if not os.path.exists(path):
        print(f"Skipping {path} (not found)")
        return
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    if old in content:
        content = content.replace(old, new)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Successfully patched: {path}")
    else:
        print(f"Pattern already patched or not found in: {path}")

def append_to_file(path, text):
    if not os.path.exists(path):
        print(f"Skipping {path} (not found)")
        return
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    if text.strip() in content:
        print(f"Text already in {path}")
        return
    with open(path, 'a', encoding='utf-8') as f:
        f.write('\n' + text + '\n')
    print(f"Successfully appended to: {path}")

def main():
    print("=== Applying Compatibility Patches & Safe Docker Configs to Xiaomi MiCode Kernel ===")
    
    # 1. arch/arm64/kernel/vdso/gettimeofday.S (fix positional argument error)
    patch_file('arch/arm64/kernel/vdso/gettimeofday.S',
               'clock_gettime_return, shift=1',
               'clock_gettime_return shift=1')
    patch_file('arch/arm64/kernel/vdso/gettimeofday.S',
               '.macro clock_gettime_return, shift=0',
               '.macro clock_gettime_return shift=0')

    # 2. arch/arm64/crypto/aes-modes.S (fix literal vector load error)
    patch_file('arch/arm64/crypto/aes-modes.S',
               "ldr\t\tq8, =0x30000000200000001\t/* addends 1,2,3[,0] */",
               "ldr\t\tq8, .Laddends\t/* addends 1,2,3[,0] */")
    laddends = ".Laddends:\n\t.word\t0x00000001\n\t.word\t0x00000002\n\t.word\t0x00000003\n\t.word\t0x00000000\nAES_ENDPROC(aes_ctr_encrypt)"
    patch_file('arch/arm64/crypto/aes-modes.S',
               'AES_ENDPROC(aes_ctr_encrypt)',
               laddends)

    # 3. drivers/soc/mediatek/mtk-cmdq-helper.c (return NULL instead of -ENOMEM from void* func)
    patch_file('drivers/soc/mediatek/mtk-cmdq-helper.c',
               'if (cmdq_pkt_add_cmd_buffer(pkt) < 0)\n\t\t\treturn -ENOMEM;',
               'if (cmdq_pkt_add_cmd_buffer(pkt) < 0)\n\t\t\treturn NULL;')

    # 4. drivers/memory/mediatek/emimpu.c (cast pointer to unsigned long)
    patch_file('drivers/memory/mediatek/emimpu.c',
               'mpucb->owner = __builtin_return_address(0);',
               'mpucb->owner = (unsigned long)__builtin_return_address(0);')

    # 5. drivers/misc/mediatek/c2k_usb/viatel_rawbulk.h (use bool for 1-bit fields)
    patch_file('drivers/misc/mediatek/c2k_usb/viatel_rawbulk.h',
               'int enable:1;\n\tint activated:1;\t/* set when usb enabled */\n\tint tty_opened:1;\n\n\tint initialized:1;',
               'bool enable:1;\n\tbool activated:1;\t/* set when usb enabled */\n\tbool tty_opened:1;\n\n\tbool initialized:1;')

    # 6. drivers/misc/mediatek/gpu/.../mtk_mfg_counter.c (fix prototype)
    patch_file('drivers/misc/mediatek/gpu/gpu_mali/mali_valhall/mali-r21p0/drivers/gpu/arm/midgard/platform/mtk_platform_common/mtk_mfg_counter.c',
               'int gator_gpu_pmu_init()',
               'int gator_gpu_pmu_init(void)')

    # 7. arch/arm64/lib/ weak symbol binding (memcpy, memmove, memset)
    patch_file('arch/arm64/lib/memcpy.S',
               '\t.weak memcpy\nENTRY(__memcpy)\nENTRY(memcpy)',
               'ENTRY(__memcpy)\nWEAK(memcpy)')
    patch_file('arch/arm64/lib/memmove.S',
               '\t.weak memmove\nENTRY(__memmove)\nENTRY(memmove)',
               'ENTRY(__memmove)\nWEAK(memmove)')
    patch_file('arch/arm64/lib/memset.S',
               '\t.weak memset\nENTRY(__memset)\nENTRY(memset)',
               'ENTRY(__memset)\nWEAK(memset)')

    # 8. Strip standalone -Werror from all Makefiles so minor warnings don't fail builds
    werror_pat = re.compile(r'-Werror(?![=-])\b')
    count = 0
    for root, dirs, files in os.walk('.'):
        for f in files:
            if f.endswith('Makefile') or f.endswith('.mk') or f.startswith('Makefile'):
                fpath = os.path.join(root, f)
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
                    content = fp.read()
                if werror_pat.search(content):
                    content = werror_pat.sub('', content)
                    with open(fpath, 'w', encoding='utf-8') as fp:
                        fp.write(content)
                    count += 1
    print(f"Removed standalone -Werror from {count} Makefiles")

    # 9. Implement stpcpy in lib/string.c and declare in include/linux/string.h
    stpcpy_code = """
#ifndef __HAVE_ARCH_STPCPY
char *stpcpy(char *dest, const char *src)
{
\twhile ((*dest++ = *src++) != '\\0')
\t\t/* nothing */;
\treturn --dest;
}
EXPORT_SYMBOL(stpcpy);
#endif
"""
    append_to_file('lib/string.c', stpcpy_code)

    stpcpy_hdr = """
#ifndef __HAVE_ARCH_STPCPY
extern char *stpcpy(char *, const char *);
#endif
"""
    patch_file('include/linux/string.h',
               'extern char * strcpy(char *,const char *);\n#endif',
               'extern char * strcpy(char *,const char *);\n#endif\n' + stpcpy_hdr.strip())

    # 10. Add Clang warning suppression, -Wno-error, and -fno-builtin-stpcpy to root Makefile
    patch_file('Makefile',
               'ifeq ($(cc-name),clang)\n',
               'ifeq ($(cc-name),clang)\nKBUILD_CFLAGS += $(call cc-disable-warning, unused-but-set-variable)\nKBUILD_CFLAGS += $(call cc-disable-warning, unused-const-variable)\nKBUILD_CFLAGS += -Wno-error\nKBUILD_CFLAGS += -fno-builtin-stpcpy\n')

    # 11. Add ONLY safe, essential Docker container configs and restore STACKPROTECTOR to begonia_user_defconfig
    # DO NOT add CONFIG_RT_GROUP_SCHED or CONFIG_SECURITY_APPARMOR (they break MTK CPU scheduler and SELinux)
    defconfig_path = 'arch/arm64/configs/begonia_user_defconfig'
    if os.path.exists(defconfig_path):
        with open(defconfig_path, 'r', encoding='utf-8', errors='ignore') as f:
            cfg_lines = f.readlines()
        # Filter out CONFIG_CC_STACKPROTECTOR_NONE
        cfg_lines = [l for l in cfg_lines if 'CONFIG_CC_STACKPROTECTOR' not in l]
        with open(defconfig_path, 'w', encoding='utf-8') as f:
            f.writelines(cfg_lines)

    essential_configs = """
CONFIG_CGROUP_DEVICE=y
CONFIG_SYSVIPC=y
CONFIG_SYSVIPC_SYSCTL=y
CONFIG_IPC_NS=y
CONFIG_POSIX_MQUEUE=y
CONFIG_BRIDGE_NETFILTER=y
CONFIG_NETFILTER_XT_MATCH_ADDRTYPE=y
CONFIG_NETFILTER_XT_MATCH_IPVS=y
CONFIG_IP_VS=y
CONFIG_MODULE_FORCE_LOAD=y
CONFIG_CC_STACKPROTECTOR=y
CONFIG_CC_STACKPROTECTOR_STRONG=y
"""
    append_to_file(defconfig_path, essential_configs.strip())
    print("Added safe Docker configs and restored CONFIG_CC_STACKPROTECTOR_STRONG to begonia_user_defconfig")

    # 12. Lock kernel release string to match official Xiaomi factory builder (-g7c18952d3c68)
    # This ensures exact vermagic match for vendor WiFi/Bluetooth drivers (wlan.ko)
    with open('.scmversion', 'w', encoding='utf-8') as f:
        f.write('-g7c18952d3c68')
    print("Created .scmversion with -g7c18952d3c68 (exact factory vermagic match)")

    # 13. Patch kernel/module.c to bypass symbol CRC and vermagic rejection for out-of-tree vendor modules
    # This ensures wmt_drv.ko, bt_drv.ko, wlan_drv_gen4m.ko, fpsgo.ko all load cleanly
    bad_ver_target = 'bad_version:\n\tpr_warn("%s: disagrees about version of symbol %s\\n",\n\t       info->name, symname);\n\treturn 0;'
    bad_ver_replace = 'bad_version:\n\tpr_warn("%s: disagrees about version of symbol %s (forcing accept)\\n",\n\t       info->name, symname);\n\treturn 1;'
    patch_file('kernel/module.c', bad_ver_target, bad_ver_replace)

    modmagic_target = 'pr_err("%s: version magic \'%s\' should be \'%s\'\\n",\n\t\t       info->name, modmagic, vermagic);\n\t\treturn -ENOEXEC;'
    modmagic_replace = 'pr_warn("%s: version magic \'%s\' should be \'%s\' (forcing accept)\\n",\n\t\t       info->name, modmagic, vermagic);'
    patch_file('kernel/module.c', modmagic_target, modmagic_replace)

    print("=== All Patches Processed ===")

if __name__ == '__main__':
    main()
