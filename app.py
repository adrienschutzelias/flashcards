import streamlit as st
import pymupdf
import os
import json
import shutil
import re
import tempfile

st.set_page_config(page_title="Convertisseur Trombinoscope", page_icon="📇")

st.title("📇 Convertisseur de Trombinoscope PDF")
st.write("Glissez-déposez le PDF de la classe ci-dessous pour générer l'archive ZIP compatible avec l'application de flashcards.")

uploaded_file = st.file_uploader("Choisissez un fichier PDF de classe", type=["pdf"])

if uploaded_file is not None:
    with tempfile.TemporaryDirectory() as tmpdirname:
        pdf_path = os.path.join(tmpdirname, uploaded_file.name)
        with open(pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        doc = pymupdf.open(pdf_path)
        
        # Détection du nom de la classe
        class_name = "Classe_Inconnue"
        for page in doc:
            page_text = page.get_text("text")
            match = re.search(r'classe\s*[:]?\s*([^\n]+)', page_text, re.IGNORECASE)
            if match:
                raw_class = match.group(1).strip()
                class_name = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in raw_class).strip().replace(' ', '_')
                break
        
        if class_name == "Classe_Inconnue":
            class_name = os.path.splitext(uploaded_file.name)[0]

        output_dir = os.path.join(tmpdirname, f"export_{class_name}")
        os.makedirs(output_dir, exist_ok=True)
        
        flashcards = []
        card_id = 1

        for page_num, page in enumerate(doc):
            image_list = page.get_images(full=True)
            words = page.get_text("words")
            
            images_info = []
            for img_index, img in enumerate(image_list):
                xref = img[0]
                rects = page.get_image_rects(xref)
                if rects:
                    r = rects[0]
                    images_info.append({'xref': xref, 'bbox': r})
            
            if not images_info:
                continue

            images_info.sort(key=lambda item: item['bbox'].y0)
            rows = []
            current_row = []
            last_y0 = None
            
            for img_item in images_info:
                y0 = img_item['bbox'].y0
                if last_y0 is None or abs(y0 - last_y0) < 25:
                    current_row.append(img_item)
                else:
                    rows.append(current_row)
                    current_row = [img_item]
                last_y0 = y0
            if current_row:
                rows.append(current_row)
            
            for row_idx, row in enumerate(rows):
                row.sort(key=lambda item: item['bbox'].x0)
                next_row_y0 = page.rect.height
                if row_idx + 1 < len(rows):
                    next_row_y0 = rows[row_idx + 1][0]['bbox'].y0

                for col_idx, img_item in enumerate(row):
                    img_rect = img_item['bbox']
                    
                    if col_idx > 0:
                        prev_rect = row[col_idx - 1]['bbox']
                        search_x0 = (prev_rect.x1 + img_rect.x0) / 2
                    else:
                        search_x0 = img_rect.x0 - 35

                    if col_idx + 1 < len(row):
                        next_rect = row[col_idx + 1]['bbox']
                        search_x1 = (img_rect.x1 + next_rect.x0) / 2
                    else:
                        search_x1 = img_rect.x1 + 35

                    search_y0 = img_rect.y1 - 5
                    search_y1 = next_row_y0 - 2

                    cell_words = []
                    for w in words:
                        wx0, wy0, wx1, wy1, wtext = w[:5]
                        clean_w = wtext.strip()
                        if not clean_w or any(meta in clean_w.lower() for meta in ["classe", "2026", "2027", "01/09"]):
                            continue
                        if wy0 >= search_y0 and wy0 < search_y1:
                            if wx0 >= search_x0 and wx1 <= search_x1:
                                cell_words.append((wy0, wx0, clean_w))
                    
                    cell_words.sort(key=lambda w: (round(w[0] / 12) * 12, w[1]))
                    full_name = " ".join([w[2] for w in cell_words])
                    
                    if not full_name:
                        full_name = f"ÉLÈVE {card_id}"
                        
                    base_image = doc.extract_image(img_item['xref'])
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    img_filename = f"eleve_{card_id:03d}.{image_ext}"
                    img_filepath = os.path.join(output_dir, img_filename)
                    
                    with open(img_filepath, "wb") as f:
                        f.write(image_bytes)
                        
                    flashcards.append({
                        "id": str(card_id),
                        "name": full_name.upper(),
                        "image": img_filename,
                        "difficult": True
                    })
                    card_id += 1

        json_path = os.path.join(output_dir, "flashcards.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(flashcards, f, ensure_ascii=False, indent=4)
        
        zip_base = shutil.make_archive(output_dir, 'zip', output_dir)
        
        with open(zip_base, "rb") as fp:
            st.success(f"Traitement réussi ! {len(flashcards)} fiches générées.")
            st.download_button(
                label="📥 Télécharger le ZIP de la classe",
                data=fp,
                file_name=f"{os.path.basename(output_dir)}.zip",
                mime="application/zip"
            )