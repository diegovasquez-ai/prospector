// Convierte el código de vinculación que entrega el puente en una imagen
// (data URL) para mostrarla en el panel. Lee el código por stdin.
import QRCode from "qrcode";

let codigo = "";
process.stdin.setEncoding("utf8");
for await (const trozo of process.stdin) codigo += trozo;
codigo = codigo.trim();
if (!codigo) process.exit(1);
process.stdout.write(await QRCode.toDataURL(codigo, { margin: 1, width: 300 }));
