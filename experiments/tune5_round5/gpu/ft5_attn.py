"""FaceTrue round 5: set the attention strength of the most recent IC-LoRA guide entry
(the photo guide) to any value, including amplification > 1.0, which the comfy LTX model
supports (comfy/ldm/lightricks/model.py) but LTXAddVideoICLoRAGuideAdvanced caps at 1.0."""
import importlib, sys
def _helper():
    for name, mod in sys.modules.items():
        if name.endswith("iclora_attention") and hasattr(mod, "set_last_guide_attention_strength"):
            return mod.set_last_guide_attention_strength
    raise RuntimeError("ComfyUI-LTXVideo iclora_attention not loaded")
class FTGuideAttentionScale:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"positive": ("CONDITIONING",), "negative": ("CONDITIONING",),
                             "attention_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 4.0, "step": 0.05})}}
    RETURN_TYPES = ("CONDITIONING", "CONDITIONING"); RETURN_NAMES = ("positive", "negative")
    FUNCTION = "run"; CATEGORY = "facetrue"
    def run(self, positive, negative, attention_strength):
        f = _helper(); return (f(positive, attention_strength), f(negative, attention_strength))
NODE_CLASS_MAPPINGS = {"FTGuideAttentionScale": FTGuideAttentionScale}
