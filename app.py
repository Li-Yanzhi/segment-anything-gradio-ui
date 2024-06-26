import gradio as gr
import gradio_image_prompter as gr_ext
# import os
from segment_anything import SamPredictor, sam_model_registry, SamAutomaticMaskGenerator
import numpy as np
import torch
import gc


title = "Segment Anything Model (SAM) Demo with Gradio"
header = (
    "<div align='center'>"
    "<h1>Segment Anything Model (SAM) Demo with Gradio</h1>"
    "</div>"
)
theme = "soft"
css = """#anno-img .mask {opacity: 0.5; transition: all 0.2s ease-in-out;}
            #anno-img .mask.active {opacity: 0.7}"""


# sam_checkpoint


def get_added_image(masks:list, image:np.ndarray):
    if len(masks)==0:
        return image
    sorted_anns = sorted(masks, key=(lambda x: x['area']), reverse=True)
    mask_all = np.zeros((sorted_anns[0]['segmentation'].shape[0], sorted_anns[0]['segmentation'].shape[1], 3))
    for ann in sorted_anns:
        m = ann["segmentation"]
        color_mask = np.random.random(3).tolist()
        mask_all[m] =  color_mask
    added_img = image /255* 0.5 + mask_all*0.5
    return added_img

def on_auto_submit_btn(auto_input_img, model_type):
    model_type = model_type
    sam_checkpoint = type2checkpoint(model_type)
    device = "cuda"
    sam = sam_model_registry[model_type](checkpoint=sam_checkpoint)
    sam.to(device=device)
    mask_generator = SamAutomaticMaskGenerator(sam)
    masks = mask_generator.generate(auto_input_img)
    added_img = get_added_image(masks, auto_input_img)
    return added_img



def on_click_submit_btn(click_input_img, model_type):
    # set sam
    model_type = model_type
    sam_checkpoint = type2checkpoint(model_type)
    device = "cuda"
    sam = sam_model_registry[model_type](checkpoint=sam_checkpoint)
    sam.to(device=device)
    predictor = SamPredictor(sam)
    predictor.set_image(click_input_img['image'])

    # set points
    np_points = np.array(click_input_img['points'])
    positive_point_conditon = (np_points[:, 2]==1) & (np_points[:, 5]==4)
    positive_points = np_points[positive_point_conditon]
    positive_points = positive_points[:, :2].tolist()
    negative_point_conditon = (np_points[:, 2]==0) & (np_points[:, 5]==4)
    negative_points = np_points[negative_point_conditon]
    negative_points = negative_points[:, :2].tolist()
    box_condition = (np_points[:, 2]==2) & (np_points[:, 5]==3)
    box_points = np_points[box_condition]
    box_points = box_points[:, [0, 1, 3, 4]].tolist()
    input_boxes = torch.tensor(box_points).to(device=predictor.device)
    transformed_boxes = predictor.transform.apply_boxes_torch(input_boxes, click_input_img['image'].shape[:2])
    masks, _, _ = predictor.predict_torch(
        point_coords=None,
        point_labels=None,
        boxes=transformed_boxes,
        multimask_output=False,
    )
    #mask = masks[0].cpu().numpy().squeeze().astype(np.uint8)*255
    masks = masks.cpu().detach().numpy()
    
    # Origin+mask
    mask_all = np.ones((click_input_img['image'].shape[0], click_input_img['image'].shape[1], 3))
    for ann in masks:
        color_mask = np.random.random((1, 3)).tolist()[0]
        for i in range(3):
            mask_all[ann[0] == True, i] = color_mask[i]
    
    img = click_input_img['image'] / 255 * 0.3 + mask_all * 0.7
    
    gc.collect()
    torch.cuda.empty_cache()

    # Segmented Image
    segmented_image = np.zeros((click_input_img['image'].shape[0], click_input_img['image'].shape[1], 4), dtype=np.uint8)
    for ann in masks:
        mask = ann[0]  # Extract the mask
        for i in range(3):
            segmented_image[:, :, i][mask == True] = click_input_img['image'][:, :, i][mask == True]
        segmented_image[:, :, 3][mask == True] = 255  # Set alpha channel to 255 for mask region

    # Cut-Out Image, Calculate bounding box, Cut image to the bounding box
    y_indices, x_indices = np.where(segmented_image[:, :, 3] == 255)
    if len(y_indices) == 0 or len(x_indices) == 0:
        raise ValueError("No objects found in the image")
    
    y_min, y_max = y_indices.min(), y_indices.max()
    x_min, x_max = x_indices.min(), x_indices.max()
    cutout_image = segmented_image[y_min:y_max + 1, x_min:x_max + 1]
 
    return img, mask_all, segmented_image, cutout_image

def on_auto_test_btn(auto_input_img):
    return auto_input_img.shape

def on_click_reset_btn():
    return None, None


examples = [["examples/chang'an univ.png"], ["examples/chd_weishui1.jpg"], ["examples/chd_weishui2.jpg"]]
click_examples = [{"image":"examples/chang'an univ.png"}, 
                  {"image":"examples/chd_weishui1.jpg"}, 
                  {"image":"examples/chd_weishui2.jpg"}] 

def type2checkpoint(model_type:str):
    return {
        "vit_b": "./models/sam_vit_b_01ec64.pth",
        "vit_l": "./models/sam_vit_l_0b3195.pth",
        "vit_h": "./models/sam_vit_h_4b8939.pth"
    }[model_type]
# type_checkpoint = {
#     "vit_b": "./models/vit_b_01ec64.pth",
#     "vit_l": "./models/vit_l_0b3195.pth",
#     "vit_h": "./models/vit_h_4b8939.pth"
# }

with gr.Blocks(title=title, theme=theme, css=css) as demo:
    gr.Markdown(header)

    with gr.Row():
        model_type = gr.Dropdown(choices=["vit_b", "vit_l", "vit_h"], 
                                label="Seclect Model", 
                                value="vit_b", 
                                multiselect=False,
                                interactive=True,
                                allow_custom_value=False,
                                filterable=False,
                                )
    with gr.Row():
        with gr.Column():

            with gr.Tab(label="Automatic") as auto_tab:
                with gr.Row():
                    auto_input_img = gr.Image(label="Input Image", 
                        sources='upload',
                        height=400, 
                        width=500,
                        show_label=True
                        )
                    # auto_output_anno_img = gr.AnnotatedImage(label="Output Image")
                    auto_output_img = gr.Image(
                        label="Output Image", 
                        interactive=False, 
                        # height=400, 
                        # width=500, 
                        show_label=True,
                        show_download_button=True
                        )
                with gr.Row():
                    auto_clr_btn=gr.ClearButton(components=[auto_input_img, auto_output_img])
                    auto_submit_btn = gr.Button("Submit")
               
                auto_submit_btn.click(
                    fn=on_auto_submit_btn,
                    inputs=[auto_input_img, model_type],
                    outputs=[auto_output_img]
                )

                with gr.Row():
                    gr.Examples(examples=examples,
                                inputs=[auto_input_img],
                                # outputs=[auto_output_img],
                                # fn=segment_everything,
                                # cache_examples=True,
                                examples_per_page=3
                                )

              

            with gr.Tab("Box") as click_tab:
                with gr.Row():
                    click_input_img = gr_ext.ImagePrompter(
                        show_label=True,
                        label="Input Image",
                        # height=400,
                        # width=500,
                        interactive=True,
                        sources='upload'
                    )
                    with gr.Tab("Image+Mask"):
                        output_img_mask = gr.Image(
                            show_label=True,
                            label="Origin+Mask Image", 
                            interactive=False, 
                            # height=400, 
                            # width=500,
                            show_download_button=True
                            )
                    with gr.Tab("Mask"):
                        output_mask = gr.Image(
                            show_label=True,
                            label="Mask Image", 
                            interactive=False, 
                            # height=400, 
                            # width=500,
                            show_download_button=True
                            )
                    with gr.Tab("Segmented Image"):
                        output_seg_img = gr.Image(
                            show_label=True,
                            label="Object Image", 
                            interactive=False, 
                            # height=400, 
                            # width=500,
                            show_download_button=True
                            )
                    with gr.Tab("Cut-Out Image"):
                        output_cutout_img = gr.Image(
                            show_label=True,
                            label="Cut-Out Image", 
                            interactive=False, 
                            # height=400, 
                            # width=500,
                            show_download_button=True
                            )
                with gr.Row():
                    click_clr_btn=gr.ClearButton(components=[click_input_img, output_img_mask, output_mask, output_seg_img, output_cutout_img])
                    # click_reset_btn = gr.Button("Clear")
                    click_submit_btn = gr.Button("Submit")
                
                click_submit_btn.click(
                    fn=on_click_submit_btn,
                    inputs=[click_input_img, model_type],
                    outputs=[output_img_mask, output_mask, output_seg_img, output_cutout_img]
                )
                with gr.Row():
                    gr.Examples(examples=click_examples,
                                inputs=[click_input_img],
                                # outputs=[auto_output_img],
                                # fn=segment_everything,
                                # cache_examples=True,
                                examples_per_page=3
                                )
    


if __name__ == "__main__":
    demo.launch()
