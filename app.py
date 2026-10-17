import streamlit as st
import pymupdf
import os
import json
import shutil
import re
import tempfile

st.set_page_config(page_title="Convertisseur Trombinoscope", page_icon="📇")

st.title("📇 Convertisseur Trombinoscope → Flashcards")
st.write("Glissez-déposez un ou plusieurs fichiers PDF de trombinoscope ci-dessous pour générer les archives ZIP compatibles avec l'appli de flashcards.")

uploaded_files = st.file_uploader("Choisissez vos fichiers PDF de trombinoscope", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    with tempfile.TemporaryDirectory() as tmpdirname:
        generated_zips = []
        
        # Barre de progression pour le traitement multiple
        progress_bar = st.progress(0)
        total_files = len(uploaded_files)
        
        for index, uploaded_file in enumerate(uploaded_files):
            # Création d'un sous-dossier temporaire pour chaque PDF
            pdf_sub_dir = os.path.join(tmpdirname, uploaded_file.name.replace(".pdf", ""))
            os.makedirs(pdf_sub_dir, exist_ok=True)
            
            pdf_path = os.path.join(pdf_sub_dir, uploaded_file.name)
            with open(pdf_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            doc = pymupdf.open(pdf_path)
            
            # Détection du nom de la classe / groupe
            class_name = "Classe_Inconnue"
            for page in doc:
                page_text = page.get_text("text")
                match = re.search(r'(?:classe|groupe)\s*[:]?\s*([^\n]+)', page_text, re.IGNORECASE)
                if match:
                    raw_class = match.group(1).strip()
                    class_name = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in raw_class).strip().replace(' ', '_')
                    break
            
            if class_name == "Classe_Inconnue":
                class_name = os.path.splitext(uploaded_file.name)[0]

            output_dir = os.path.join(pdf_sub_dir, f"export_{class_name}")
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
            generated_zips.append((f"{os.path.basename(output_dir)}.zip", zip_base, len(flashcards)))
            
            # Mise à jour de la barre de progression
            progress_bar.progress((index + 1) / total_files)

        st.success(f"Traitement réussi ! {len(generated_zips)} fichier(s) converti(s).")
        
        st.markdown("### 📥 Télécharger les archives ZIP générées")
        for zip_name, zip_path, count in generated_zips:
            with open(zip_path, "rb") as fp:
                st.download_button(
                    label=f"📥 Télécharger {zip_name} ({count} fiches)",
                    data=fp.read(),
                    file_name=zip_name,
                    mime="application/zip",
                    key=zip_name  # Clé unique indispensable pour chaque bouton dans une boucle Streamlit
                )
st.subheader("Tutoriel :")
st.caption("- Téléchargez tous les trombinoscopes de vos classes via Ecole Directe, dans Consultation/Les éditions/Trombinoscope")
st.caption("- Uploadez votre ou vos pdf. Pour plusieurs PDF d’un coup sur mobile il faut faire un appui long sur le premier jusqu’à ce qu’il soit sélectionné, puis des appuis courts sur les suivants, et valider ensuite (s'il ne se passe rien, rafraichissez la page et recommencez).")
st.caption("- Téléchargez le(s) ZIP fourni(s) en sortie (si plusieurs PDF d’un coup, il y aura un bouton par fichier ZIP à télécharger)")
st.caption("- Dans l'application de flash cards, cliquez sur le bouton bleu 'CRÉER UN JEU (IMPORT ZIP)'")
st.caption("- Retrouvez le(s) fichier(s) ZIP téléchargé(s) dans votre dossier téléchargement. Vous pouvez en importer plusieurs d’un coup en faisant un appui long sur le premier, puis un appui court sur les suivant et enfin valider")