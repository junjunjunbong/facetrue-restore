#!/bin/bash
cd ~/facetrue-extra/r4; W=~/facetrue-extra/r4/w
./pdl.sh h94/IP-Adapter sdxl_models/ip-adapter-plus-face_sdxl_vit-h.safetensors 847517512 $W/ipa
./pdl.sh SG161222/RealVisXL_V4.0 vae/diffusion_pytorch_model.fp16.safetensors 167335342 $W/realvis
./pdl.sh SG161222/RealVisXL_V4.0 text_encoder/model.fp16.safetensors 246144864 $W/realvis
./pdl.sh SG161222/RealVisXL_V4.0 text_encoder_2/model.fp16.safetensors 1389382880 $W/realvis
./pdl.sh SG161222/RealVisXL_V4.0 unet/diffusion_pytorch_model.fp16.safetensors 5135149760 $W/realvis
./pdl.sh InstantX/InstantID ip-adapter.bin 1691134141 $W/instantid
./pdl.sh InstantX/InstantID ControlNetModel/diffusion_pytorch_model.safetensors 2502139136 $W/instantid
echo ALLDONE
