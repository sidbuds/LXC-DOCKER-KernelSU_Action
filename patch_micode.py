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

def main():
    print("=== Applying Clang 14 Compatibility Patches to Xiaomi MiCode Kernel ===")
    
    # 1. arch/arm64/kernel/vdso/gettimeofday.S
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

    # 7. Strip standalone -Werror from all Makefiles so minor warnings don't fail builds
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

    # 8. Add Clang warning suppression and -Wno-error to root Makefile
    patch_file('Makefile',
               'ifeq ($(cc-name),clang)\n',
               'ifeq ($(cc-name),clang)\nKBUILD_CFLAGS += $(call cc-disable-warning, unused-but-set-variable)\nKBUILD_CFLAGS += $(call cc-disable-warning, unused-const-variable)\nKBUILD_CFLAGS += -Wno-error\n')

    print("=== All Patches Processed ===")

if __name__ == '__main__':
    main()
