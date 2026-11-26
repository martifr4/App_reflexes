"""Every customer-facing sentence the assistant can say without the language model.

Catalan and Spanish always use the formal plural (vostès / ustedes). French uses "vous".
Placeholders: {shop}, {file}, {low}, {high}, ...
"""
from __future__ import annotations

T: dict[str, dict[str, str]] = {
    "greeting": {
        "ca": "Hola! Sóc l'assistent virtual de {shop}, un sistema d'intel·ligència artificial. Els ajudo a preparar una sol·licitud de pressupost: poden adjuntar el plànol (DXF, DWG, STEP o PDF) i indicar material, gruix i quantitat. Els donaré un preu orientatiu, i un tècnic de {shop} els confirmarà el pressupost definitiu.",
        "es": "¡Hola! Soy el asistente virtual de {shop}, un sistema de inteligencia artificial. Les ayudo a preparar una solicitud de presupuesto: pueden adjuntar el plano (DXF, DWG, STEP o PDF) e indicar material, espesor y cantidad. Les daré un precio orientativo, y un técnico de {shop} les confirmará el presupuesto definitivo.",
        "en": "Hello! I'm {shop}'s virtual assistant, an AI system. I can help you prepare a quote request: attach your drawing (DXF, DWG, STEP or PDF) and tell me the material, thickness and quantity. I'll give you an indicative price, and a technician at {shop} will confirm the final quote.",
        "fr": "Bonjour ! Je suis l'assistant virtuel de {shop}, un système d'intelligence artificielle. Je vous aide à préparer votre demande de devis : vous pouvez joindre le plan (DXF, DWG, STEP ou PDF) et indiquer la matière, l'épaisseur et la quantité. Je vous donnerai un prix indicatif, et un technicien de {shop} vous confirmera le devis définitif.",
    },
    "ask_drawing": {
        "ca": "Poden adjuntar el plànol de la peça (preferiblement en DXF)? Si no en tenen, indiquin les mides (per exemple: 200 x 150 mm amb 4 forats).",
        "es": "¿Pueden adjuntar el plano de la pieza (preferiblemente en DXF)? Si no lo tienen, indiquen las medidas (por ejemplo: 200 x 150 mm con 4 agujeros).",
        "en": "Could you attach the part drawing (DXF if possible)? If you don't have one, give me the dimensions (for example: 200 x 150 mm with 4 holes).",
        "fr": "Pouvez-vous joindre le plan de la pièce (de préférence en DXF) ? Sinon, indiquez les dimensions (par exemple : 200 x 150 mm avec 4 trous).",
    },
    "ask_material": {
        "ca": "Quin material necessiten (acer al carboni, inoxidable 304 o 316, alumini, galvanitzat…)?",
        "es": "¿Qué material necesitan (acero al carbono, inoxidable 304 o 316, aluminio, galvanizado…)?",
        "en": "Which material do you need (mild steel, stainless 304 or 316, aluminium, galvanised…)?",
        "fr": "Quelle matière souhaitez-vous (acier, inox 304 ou 316, aluminium, galvanisé…) ?",
    },
    "ask_thickness": {
        "ca": "Quin gruix té la xapa, en mm?",
        "es": "¿Qué espesor tiene la chapa, en mm?",
        "en": "What is the sheet thickness, in mm?",
        "fr": "Quelle est l'épaisseur de la tôle, en mm ?",
    },
    "ask_quantity": {
        "ca": "Quantes peces necessiten?",
        "es": "¿Cuántas piezas necesitan?",
        "en": "How many parts do you need?",
        "fr": "Combien de pièces vous faut-il ?",
    },
    "ask_bends": {
        "ca": "Quants plecs té cada peça?",
        "es": "¿Cuántos pliegues tiene cada pieza?",
        "en": "How many bends does each part have?",
        "fr": "Combien de plis a chaque pièce ?",
    },
    "ask_deadline": {
        "ca": "Per a quan les necessiten?",
        "es": "¿Para cuándo las necesitan?",
        "en": "When do you need them?",
        "fr": "Pour quand en avez-vous besoin ?",
    },
    "ask_finish": {
        "ca": "Necessiten algun acabat (desbarbat, pintura en pols, galvanitzat en calent) o les volen sense acabat?",
        "es": "¿Necesitan algún acabado (desbarbado, pintura en polvo, galvanizado en caliente) o las quieren sin acabado?",
        "en": "Do you need a finish (deburring, powder coating, hot-dip galvanising), or none?",
        "fr": "Souhaitez-vous une finition (ébavurage, peinture poudre, galvanisation à chaud) ou aucune ?",
    },
    "ask_name": {
        "ca": "Per passar-ho a l'equip comercial, ens poden indicar un nom de contacte i l'empresa?",
        "es": "Para pasarlo al equipo comercial, ¿nos pueden indicar un nombre de contacto y la empresa?",
        "en": "To pass this to the sales team, could you give me a contact name and your company?",
        "fr": "Pour transmettre la demande à l'équipe commerciale, pouvez-vous m'indiquer un nom de contact et votre entreprise ?",
    },
    "ask_contact": {
        "ca": "I un correu electrònic o un telèfon on els puguem enviar el pressupost definitiu?",
        "es": "¿Y un correo electrónico o un teléfono donde les podamos enviar el presupuesto definitivo?",
        "en": "And an email address or phone number where we can send you the final quote?",
        "fr": "Et une adresse e-mail ou un téléphone pour vous envoyer le devis définitif ?",
    },
    "ask_delivery": {
        "ca": "On caldria lliurar les peces (població, o recollida al taller)?",
        "es": "¿Dónde habría que entregar las piezas (población, o recogida en el taller)?",
        "en": "Where should the parts be delivered (town, or collection at the workshop)?",
        "fr": "Où faut-il livrer les pièces (ville, ou retrait à l'atelier) ?",
    },
    "estimate_intro": {
        "ca": "Amb aquestes dades, el preu orientatiu és de {low}–{high} € (sense IVA ni transport). És una estimació automàtica pendent de revisió: el pressupost vinculant el confirmarà un tècnic de {shop}.",
        "es": "Con estos datos, el precio orientativo es de {low}–{high} € (sin IVA ni transporte). Es una estimación automática pendiente de revisión: el presupuesto vinculante lo confirmará un técnico de {shop}.",
        "en": "With this information, the indicative price is €{low}–{high} (excluding VAT and delivery). It's an automatic estimate pending review: a technician at {shop} will confirm the binding quote.",
        "fr": "Avec ces informations, le prix indicatif est de {low} à {high} € HT (hors livraison). C'est une estimation automatique en attente de vérification : un technicien de {shop} confirmera le devis définitif.",
    },
    "estimate_updated": {
        "ca": "He actualitzat el preu orientatiu: {low}–{high} € (sense IVA ni transport), pendent de revisió.",
        "es": "He actualizado el precio orientativo: {low}–{high} € (sin IVA ni transporte), pendiente de revisión.",
        "en": "I've updated the indicative price: €{low}–{high} (excluding VAT and delivery), pending review.",
        "fr": "J'ai mis à jour le prix indicatif : {low} à {high} € HT (hors livraison), en attente de vérification.",
    },
    "no_price": {
        "ca": "Amb la informació disponible no puc calcular un preu fiable. Un tècnic de {shop} ho revisarà i es posarà en contacte amb vostès.",
        "es": "Con la información disponible no puedo calcular un precio fiable. Un técnico de {shop} lo revisará y se pondrá en contacto con ustedes.",
        "en": "With the information available I can't calculate a reliable price. A technician at {shop} will review it and get back to you.",
        "fr": "Avec les informations disponibles, je ne peux pas calculer un prix fiable. Un technicien de {shop} l'examinera et vous recontactera.",
    },
    "handoff": {
        "ca": "Gràcies, {name}. Hem passat la sol·licitud a l'equip comercial de {shop}, que els enviarà el pressupost definitiu. Si volen, poden afegir aquí més plànols o comentaris.",
        "es": "Gracias, {name}. Hemos pasado la solicitud al equipo comercial de {shop}, que les enviará el presupuesto definitivo. Si quieren, pueden añadir aquí más planos o comentarios.",
        "en": "Thank you, {name}. We've passed your request to the {shop} sales team, who will send you the final quote. You can add more drawings or comments here.",
        "fr": "Merci, {name}. Votre demande a été transmise à l'équipe commerciale de {shop}, qui vous enverra le devis définitif. Vous pouvez ajouter ici d'autres plans ou commentaires.",
    },
    "after_handoff": {
        "ca": "Ho he afegit a la seva sol·licitud. L'equip comercial ho tindrà en compte.",
        "es": "Lo he añadido a su solicitud. El equipo comercial lo tendrá en cuenta.",
        "en": "I've added that to your request. The sales team will take it into account.",
        "fr": "Je l'ai ajouté à votre demande. L'équipe commerciale en tiendra compte.",
    },
    "question_noted": {
        "ca": "He anotat la seva pregunta perquè l'equip comercial els la respongui.",
        "es": "He anotado su pregunta para que el equipo comercial se la responda.",
        "en": "I've noted your question so the sales team can answer it.",
        "fr": "J'ai noté votre question pour que l'équipe commerciale vous réponde.",
    },
    "off_topic": {
        "ca": "Només puc ajudar amb sol·licituds de pressupost i comandes de {shop}.",
        "es": "Solo puedo ayudar con solicitudes de presupuesto y pedidos de {shop}.",
        "en": "I can only help with quote requests and orders for {shop}.",
        "fr": "Je peux seulement vous aider pour les demandes de devis et les commandes de {shop}.",
    },
    "file_dxf": {
        "ca": "He llegit el plànol {file}: {w} × {h} mm, {cut} m de tall i {pierces} perforacions{bends}.",
        "es": "He leído el plano {file}: {w} × {h} mm, {cut} m de corte y {pierces} perforaciones{bends}.",
        "en": "I've read the drawing {file}: {w} × {h} mm, {cut} m of cutting and {pierces} pierces{bends}.",
        "fr": "J'ai lu le plan {file} : {w} × {h} mm, {cut} m de découpe et {pierces} amorçages{bends}.",
    },
    "file_dxf_bends": {"ca": ", amb {n} plec(s)", "es": ", con {n} pliegue(s)", "en": ", with {n} bend(s)", "fr": ", avec {n} pli(s)"},
    "file_other": {
        "ca": "Hem rebut {file}. Aquest format el revisarà un tècnic; mentrestant, recollim les dades per al pressupost.",
        "es": "Hemos recibido {file}. Este formato lo revisará un técnico; mientras tanto, recogemos los datos para el presupuesto.",
        "en": "We've received {file}. A technician will review this format; in the meantime, let's collect the details for the quote.",
        "fr": "Nous avons bien reçu {file}. Un technicien examinera ce format ; en attendant, rassemblons les informations du devis.",
    },
    "file_error": {
        "ca": "No he pogut llegir {file} automàticament. El revisarà un tècnic.",
        "es": "No he podido leer {file} automáticamente. Lo revisará un técnico.",
        "en": "I couldn't read {file} automatically. A technician will review it.",
        "fr": "Je n'ai pas pu lire {file} automatiquement. Un technicien l'examinera.",
    },
    "file_rejected": {
        "ca": "Aquest tipus de fitxer no s'admet. Poden enviar DXF, DWG, STEP, PDF o imatges (màxim 20 MB).",
        "es": "Este tipo de archivo no se admite. Pueden enviar DXF, DWG, STEP, PDF o imágenes (máximo 20 MB).",
        "en": "This file type isn't accepted. You can send DXF, DWG, STEP, PDF or images (20 MB max).",
        "fr": "Ce type de fichier n'est pas accepté. Vous pouvez envoyer DXF, DWG, STEP, PDF ou des images (20 Mo max).",
    },
    "card_title": {
        "ca": "Preu orientatiu · pendent de revisió",
        "es": "Precio orientativo · pendiente de revisión",
        "en": "Indicative price · pending review",
        "fr": "Prix indicatif · en attente de vérification",
    },
    "confidence": {"ca": "Fiabilitat", "es": "Fiabilidad", "en": "Confidence", "fr": "Fiabilité"},
    "per_unit": {"ca": "per peça", "es": "por pieza", "en": "per part", "fr": "par pièce"},
}

CONFIDENCE = {
    "high": {"ca": "alta", "es": "alta", "en": "high", "fr": "élevée"},
    "medium": {"ca": "mitjana", "es": "media", "en": "medium", "fr": "moyenne"},
    "low": {"ca": "baixa", "es": "baja", "en": "low", "fr": "faible"},
}

PROCESS = {
    "laser": {"ca": "tall làser", "es": "corte láser", "en": "laser cutting", "fr": "découpe laser"},
    "bending": {"ca": "plegat", "es": "plegado", "en": "bending", "fr": "pliage"},
    "welding": {"ca": "soldadura", "es": "soldadura", "en": "welding", "fr": "soudure"},
    "machining": {"ca": "mecanitzat", "es": "mecanizado", "en": "machining", "fr": "usinage"},
}

# Short lines under the price card, one per engine note code
NOTES = {
    "quantity_discount": {"ca": "Inclou descompte per quantitat ({pct} %)", "es": "Incluye descuento por cantidad ({pct} %)", "en": "Includes a quantity discount ({pct}%)", "fr": "Remise quantité incluse ({pct} %)"},
    "rush_surcharge": {"ca": "Inclou recàrrec d'urgència ({pct} %)", "es": "Incluye recargo de urgencia ({pct} %)", "en": "Includes a rush surcharge ({pct}%)", "fr": "Majoration d'urgence incluse ({pct} %)"},
    "standard_lead_time": {"ca": "Termini de lliurament estàndard", "es": "Plazo de entrega estándar", "en": "Standard lead time", "fr": "Délai standard"},
    "minimum_order": {"ca": "S'aplica la comanda mínima ({min} €)", "es": "Se aplica el pedido mínimo ({min} €)", "en": "Minimum order applies (€{min})", "fr": "Minimum de commande appliqué ({min} €)"},
    "excludes_vat_and_delivery": {"ca": "Sense IVA ni transport", "es": "Sin IVA ni transporte", "en": "Excluding VAT and delivery", "fr": "HT, hors livraison"},
    "geometry_described": {"ca": "Mides indicades per vostès, sense plànol", "es": "Medidas indicadas por ustedes, sin plano", "en": "Dimensions you gave us, no drawing", "fr": "Dimensions indiquées, sans plan"},
    "geometry_warning": {"ca": "El plànol pot tenir errors: cal revisió", "es": "El plano puede tener errores: requiere revisión", "en": "The drawing may have errors: needs review", "fr": "Le plan peut contenir des erreurs : à vérifier"},
    "bends_unknown": {"ca": "Plegat pendent: falta el nombre de plecs", "es": "Plegado pendiente: falta el número de pliegues", "en": "Bending not included: number of bends unknown", "fr": "Pliage non inclus : nombre de plis inconnu"},
    "bends_from_drawing": {"ca": "{bends} plec(s) llegit(s) del plànol", "es": "{bends} pliegue(s) leído(s) del plano", "en": "{bends} bend(s) read from the drawing", "fr": "{bends} pli(s) lu(s) sur le plan"},
    "bending_out_of_range": {"ca": "Plegat fora de rang: ho valorarà un tècnic", "es": "Plegado fuera de rango: lo valorará un técnico", "en": "Bending out of range: a technician will price it", "fr": "Pliage hors limites : à chiffrer par un technicien"},
    "welding_needs_review": {"ca": "La soldadura la valorarà un tècnic", "es": "La soldadura la valorará un técnico", "en": "A technician will price the welding", "fr": "La soudure sera chiffrée par un technicien"},
    "process_not_priced": {"ca": "{process}: ho valorarà un tècnic", "es": "{process}: lo valorará un técnico", "en": "{process}: a technician will price it", "fr": "{process} : à chiffrer par un technicien"},
    "finish_not_priced": {"ca": "Acabat pendent de valorar", "es": "Acabado pendiente de valorar", "en": "Finish not yet priced", "fr": "Finition à chiffrer"},
    "unpriced_file": {"ca": "{file}: el revisarà un tècnic", "es": "{file}: lo revisará un técnico", "en": "{file}: a technician will review it", "fr": "{file} : sera examiné par un technicien"},
    "part_too_large": {"ca": "Peça més gran que la màquina: cal revisió", "es": "Pieza mayor que la máquina: requiere revisión", "en": "Part larger than the machine: needs review", "fr": "Pièce plus grande que la machine : à vérifier"},
    "thickness_out_of_range": {"ca": "Gruix fora del rang habitual: ho valorarà un tècnic", "es": "Espesor fuera del rango habitual: lo valorará un técnico", "en": "Thickness outside the usual range: a technician will price it", "fr": "Épaisseur hors gamme : à chiffrer par un technicien"},
    "material_not_listed": {"ca": "Material no habitual: ho valorarà un tècnic", "es": "Material no habitual: lo valorará un técnico", "en": "Unusual material: a technician will price it", "fr": "Matière inhabituelle : à chiffrer par un technicien"},
}

LANGS = ("ca", "es", "en", "fr")


def t(key: str, lang: str, **kw) -> str:
    table = T[key]
    return table.get(lang, table["en"]).format(**kw)


def render_note(note: dict, lang: str) -> str | None:
    tmpl = NOTES.get(note["code"])
    if not tmpl:
        return None
    p = dict(note.get("params", {}))
    if "discount" in p:
        p["pct"] = round(p["discount"] * 100)
    if "surcharge" in p:
        p["pct"] = round(p["surcharge"] * 100)
    if "minimum" in p:
        p["min"] = f"{p['minimum']:.0f}"
    if "process" in p:
        p["process"] = PROCESS.get(p["process"], {}).get(lang, p["process"]).capitalize()
    try:
        return tmpl.get(lang, tmpl["en"]).format(**p)
    except KeyError:
        return None
