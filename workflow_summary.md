# 工作流输入参数汇总

## 一、模型文件需求

### 1. 单图编辑
- **Checkpoint**: Qwen-Rapid-AIO-NSFW-v18.safetensors
- **UNET**: 无
- **VAE**: 无
- **CLIP**: qwen_2.5_vl_7b_fp8_scaled.safetensors
- **LoRA**: Qwen-Image-Edit-F2P.safetensors
- **输入图片**: ComfyUI_00130_.png (需要替换)

### 2. 单图出分镜图
- **Checkpoint**: Qwen-Rapid-AIO-NSFW-v13.safetensors
- **UNET**: 无
- **VAE**: 无
- **CLIP**: 无
- **LoRA**: Qwen\Qwen-Image-Edit-F2P.safetensors
- **输入图片**: de4b3edc18b71f19d3d79e8250e66880.jpg (需要替换)

### 3. 双图编辑+姿态迁移
- **Checkpoint**: Qwen-Rapid-AIO-NSFW-v18.safetensors
- **UNET**: 无
- **VAE**: 无
- **CLIP**: qwen_2.5_vl_7b_fp8_scaled.safetensors
- **LoRA**: Qwen-Image-Edit-F2P.safetensors
- **输入图片**: 2张 (ComfyUI_temp_epbeq_00002_.png, IMG_20251217_120321_632 (1).jpg) (需要替换)

### 4. 三图编辑
- **Checkpoint**: Qwen-Rapid-AIO-NSFW-v18.safetensors
- **UNET**: 无
- **VAE**: 无
- **CLIP**: qwen_2.5_vl_7b_fp8_scaled.safetensors
- **LoRA**: Qwen-Image-Edit-F2P.safetensors
- **输入图片**: 3张 (IMG_20251217_120321_632 (1).jpg, ComfyUI_00001_tdpmz_1766671653.png, �־�1β֡.png) (需要替换)

### 5. 单图可视化出多角度
- **Checkpoint**: Qwen-Rapid-AIO-NSFW-v18.safetensors
- **UNET**: 无
- **VAE**: 无
- **CLIP**: qwen_2.5_vl_7b_fp8_scaled.safetensors
- **LoRA**: Qwen-Image-Edit-F2P.safetensors
- **输入图片**: pic1.png (需要替换)

### 6. Z-image 高清出图
- **Checkpoint**: 无
- **UNET**: z_image_turbo_bf16.safetensors ✓
- **VAE**: zimage ae.safetensors ✓
- **CLIP**: qwen_3_4b.safetensors ✓
- **LoRA**: 无
- **输入图片**: 无
- **注意**: 此工作流不需要输入图片，是文生图模式

### 7. 自动反推洗图+sd放大
- **Checkpoint**: 无
- **UNET**: z_image_turbo_bf16.safetensors ✓
- **VAE**: zimage ae.safetensors ✓
- **CLIP**: qwen_3_4b.safetensors ✓
- **LoRA**: 无
- **输入图片**: 60223acc8b25ac8637a0df069048a23467c2242a318b48073cbe47830d6797d0.jpg (需要替换)

### 8. 图片sd放大
- **Checkpoint**: 无
- **UNET**: 无
- **VAE**: 无
- **CLIP**: 无
- **LoRA**: 无
- **输入图片**: rgthree.compare._temp_oujyo_00034_.png (需要替换)
- **注意**: 可能依赖SD放大模型

### 9. 双采样超多细节文生图
- **Checkpoint**: 无
- **UNET**: z_image_turbo_bf16.safetensors, flux-2-klein-9b.safetensors ✓
- **VAE**: flux2-vae.safetensors, zimage ae.safetensors ✓
- **CLIP**: qwen_3_8b.safetensors, qwen_3_4b.safetensors ✓
- **LoRA**: zit_fdpo_v1.safetensors, Kook_Zimage_��ʵ����_Turbo.safetensors
- **输入图片**: 无 (纯文生图)

### 10-11. LTX 文&图生视频
- **Checkpoint**: ltx-2.3-22b-dev-fp8.safetensors ✓
- **UNET**: 无
- **VAE**: 无
- **CLIP**: 无
- **LoRA**: ltx-2.3-22b-distilled-lora-384-1.1.safetensors, ������Ļ��������һ����.safetensors
- **输入图片**: pic1.png (需要替换)

### 12. LTX 首尾帧视频
- **Checkpoint**: ltx-2.3-22b-dev-fp8.safetensors ✓
- **UNET**: 无
- **VAE**: 无
- **CLIP**: 无
- **LoRA**: ltx-2.3-22b-distilled-lora-384-1.1.safetensors
- **输入图片**: 1.png, 2.png (需要替换) - 需要两张图片作为首尾帧

### 13. LTX 单人对口型
- **Checkpoint**: ltx-2.3-22b-dev-fp8.safetensors ✓
- **UNET**: 无
- **VAE**: 无
- **CLIP**: 无
- **LoRA**: ltx-2.3-22b-distilled-lora-384-1.1.safetensors
- **输入图片**: concert-scene-02-side-profile.png (需要替换)

### 14. LTX 双人对话
- **Checkpoint**: 无
- **UNET**: ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors ✓
- **VAE**: 无
- **CLIP**: 无
- **LoRA**: 无
- **输入图片**: 8d1173a0d341f2a8927682098450b4a63a4ca4236a56cd53ac7d4030b629301c.png (需要替换)

### 15. LTX 多图参考
- **Checkpoint**: 无
- **UNET**: ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors ✓
- **VAE**: 无
- **CLIP**: 无
- **LoRA**: ltx-2.3-22b-distilled-lora-384-1.1.safetensors
- **输入图片**: 5张 (6bd63d926a91c355e6bc06ba50571d5257cfaa3cbcf59d2e70670abc2a9a772d.png x2, 1.png, 2.png, 6.png) (需要替换)

---

## 二、ComfyUI 已有的模型

### Checkpoints (2个)
- Qwen-Rapid-AIO-NSFW-v18.safetensors ✓
- ltx-2.3-22b-dev-fp8.safetensors ✓

### UNETs (6个)
- z_image_turbo_bf16.safetensors ✓
- ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors ✓
- flux-2-klein-9b.safetensors ✓
- Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors
- MelBandRoformer_fp16.safetensors
- MelBandRoformer_fp32.safetensors

### VAEs (8个)
- zimage ae.safetensors ✓
- flux2-vae.safetensors ✓
- LTX23_audio_vae_bf16.safetensors
- LTX23_video_vae_bf16.safetensors
- ema_vae_fp16.safetensors
- taeltx2_3.safetensors
- wan_2.1_vae.safetensors
- pixel_space

### CLIPs (7个)
- qwen_2.5_vl_7b_fp8_scaled.safetensors ✓
- qwen_3_4b.safetensors ✓
- qwen_3_8b.safetensors ✓
- gemma_3_12B_it_fp4_mixed.safetensors
- gemma_3_12B_it_fpmixed.safetensors
- ltx-2.3_text_projection_bf16.safetensors
- umt5-xxl-enc-bf16.safetensors

---

## 三、KSampler 采样参数

| 工作流 | seed | steps | cfg | sampler_name | scheduler | denoise |
|--------|------|-------|-----|--------------|-----------|---------|
| 1.单图编辑 | randomize → 0 | 4 | 1 | euler_ancestral | simple | 1 |
| 3.双图编辑+姿态迁移 | randomize → 0 | 4 | 1 | euler_ancestral | beta57 | 1 |
| 4.三图编辑 | randomize → 0 | 4 | 1 | euler_ancestral | beta57 | 1 |
| 5.单图可视化出多角度 | randomize → 0 | 6 | 1 | euler_ancestral | simple | 1 |
| 6.Z-image高清出图 | randomize → 0 | 9 | 1 | euler | simple | 1 |
| 7.自动反推洗图+sd放大 | randomize → 0 | 10 | 1 | euler | simple | 0.6 |

**注意**: LTX视频类工作流(10-15)使用不同的采样器结构

---

## 四、可调参数说明

### 必换输入
1. **LoadImage节点** - 所有引用本地图片的工作流，图片路径需要替换为实际存在的图片
2. **LoRA模型** - 部分工作流引用的LoRA文件可能不存在

### KSampler参数调整
- **seed (种子)**: 随机种子会影响生成结果，randomize需要改为具体数字如0
- **steps (步数)**: 影响生成质量，通常4-30之间
- **cfg (引导强度)**: 通常1-10之间
- **sampler_name (采样器)**: euler, euler_ancestral, dpmpp_2m等
- **scheduler (调度器)**: simple, karras, beta57等
- **denoise (降噪)**: 0.0-1.0之间，1.0表示完全重新生成

### 分辨率
- 默认通常是 512x512, 720x1280, 1024x1024 等
- 可通过 EmptyLatentImage 或 ImageResize 节点调整

---

## 五、工作流分类

### 图片编辑类 (1-5)
需要: Checkpoint + CLIP + LoRA + 输入图片
特点: 基于Qwen模型的图像编辑

### 高清出图类 (6-7)
需要: UNET + VAE + CLIP + (可选输入图片)
特点: Z-image Turbo模型，文生图或图生图

### 视频生成类 (10-15)
需要: Checkpoint/UNET + LoRA + 输入图片(用于参考/首尾帧)
特点: LTX 2.3模型，视频生成

---

## 六、测试文件

桌面test文件夹已有:
- image1.png - 可用于LoadImage
- image2.png - 可用于LoadImage
- music.mp3 - 可用于PlaySound
- vedio.mp4 - 视频文件