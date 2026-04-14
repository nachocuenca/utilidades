import requests
import json

prompt = '''Extrae los siguientes campos de la factura en formato JSON:
- nombre_proveedor
- nif_proveedor
- nombre_cliente
- nif_cliente
- cp_cliente
- numero_factura
- fecha_factura
- subtotal
- iva
- total

Texto OCR:
Página : 1
BEROIL, S.L.U CLIENTE:
PLAZA MAYOR, S/N
SUMINISTROS DE OFICINA BENIOFFI S
09559 Los Altos (Dobro) SUMINISTROS DE OFICINA BENIOFFI S
C/ Beniarda - pg ind la Alberca, 13 - LC
BURGOS 03530 NUCIA, LA C/ Beniarda - pg ind la Alberca, 13 - LC
Tlf. 947473302Fax 947473301 03530 NUCIA, LA
ALICANTE / ALACANT
CIF: B09417957 ALICANTE / ALACANT
FECHA 31/03/2026 CODIGO CLIENTE000110790 NIFB53711495 FACTURA NÚM:26D013477
CANTIDAD CONCEPTO PRECIO UNITARIO DESCUENTO SUBTOTAL
20.01 S/P 95 GASOLINA E5 1.4990 € 30.00 €
6.54 S/P 95 GASOLINA E5 1.5290 € 10.00 €
18.88 S/P 95 GASOLINA E5 1.5890 € 30.00 €
FORMA DE PAGO: Impuestos especiales incluidos en el precio (€ x litro):
T.ESTATAL T.AUTONOMICO LITROS IMPORTE
No CUENTA ES78 0081 5373 1500 0105 0006 (General y Estatal 0.359) x 20.01 litros 7.18 €
FACTURA COBRADA (General y Estatal 0.504) x 25.42 litros 12.81 €
BASE IMPONIBLE % IVA SUBTOTAL
33.06 € 21 6.94 € 40.00 €
27.27 € 10 2.73 € 30.00 €
EFECTIVO
Reg. Merc. de Burgos, Libro 204 Folio 114 Inscripción 8 Hoja BU-70028
BEROIL S.L. es el Responsable del tratamiento de sus datos personales y le informa de que estos datos serán tratados de conformidad con lo dispuesto
TOTAL FACTURA
en el reglamento (UE) 2016/679, de 27 de abril (GDPR), y la Ley Orgánica 3/2018, de 5 diciembre (LOPDGDD), con la finalidad de mantener una relación
comercial (en base a una relación contractual, obligación legal o interés legítimo) y conservarlos durante no más tiempo del necesario para mantener 70.00 €
el fin del tratamiento o mientras existan prescripciones legales que dictaminen su custodia. No se comunicarán los datos a terceros, salvo obligación
legal. Asimismo, se le informa de que puede ejercer sus derechos de acceso, rectificación, portabilidad y supresión de sus datos y los de limitación
y oposición a su tratamiento dirigiéndose a BEROIL S.L en Crta. Madrid Irún KM 247, -09199 Rubena (Burgos). Email: administracionhuidobro@beroil.es y
el de reclamación a www.aepd.es'''

payload = {
    "model": "qwen2.5vl:7b",
    "prompt": prompt
}

resp = requests.post("http://localhost:11434/api/generate", json=payload)
try:
    data = resp.json()
    # Ollama puede devolver la respuesta en 'response' o similar
    print(data.get('response', data))
except Exception:
    print(resp.text)
