/**
 * APP VECINOS CALANDRIAS - BACKEND GOOGLE APPS SCRIPT
 */

// 1. FUNCIÓN DE PRUEBA Y AUTORIZACIÓN DIRECTA
function autorizar() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  Logger.log("Conectado con éxito a la planilla: " + ss.getName());
}

// 2. LECTURA DE DATOS (doGet)
function doGet(e) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  // Hoja 1: Padrón de Vecinos (primera pestaña)
  var sheetVecinos = ss.getSheets()[0];
  var dataVecinos = sheetVecinos.getDataRange().getValues();

  // Hoja 2: Directorio Telefónico
  var sheetTelefonos = ss.getSheetByName("Directorio_Telefonos");
  var dataTelefonos = [];

  if (sheetTelefonos) {
    dataTelefonos = sheetTelefonos.getDataRange().getValues();
  }

  var responsePayload = {
    vecinos: dataVecinos,
    telefonos: dataTelefonos
  };

  return ContentService.createTextOutput(JSON.stringify(responsePayload))
    .setMimeType(ContentService.MimeType.JSON);
}

// 3. ESCRITURA Y ACCIONES (doPost)
function doPost(e) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var lock = LockService.getScriptLock();

  try {
    lock.waitLock(10000);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: "El servidor está ocupado. Intente nuevamente."
    })).setMimeType(ContentService.MimeType.JSON);
  }

  try {
    var body = JSON.parse(e.postData.contents);
    var action = body.action;

    // ALTA DE TELÉFONO
    if (action === "add_phone") {
      var sheetTel = ss.getSheetByName("Directorio_Telefonos");
      if (!sheetTel) {
        sheetTel = ss.insertSheet("Directorio_Telefonos");
        sheetTel.appendRow(["ID", "TARJETA", "CATEGORIA", "NOMBRE", "TELEFONO", "ACTIVO"]);
      }

      var d = body.data;
      sheetTel.appendRow([
        d.ID || "",
        d.TARJETA || "UTILES",
        d.CATEGORIA || "General",
        d.NOMBRE || "",
        d.TELEFONO || "",
        d.ACTIVO || "SI"
      ]);

      return ContentService.createTextOutput(JSON.stringify({
        status: "ok",
        message: "Teléfono registrado exitosamente"
      })).setMimeType(ContentService.MimeType.JSON);
    }

    // BAJA LÓGICA DE TELÉFONO
    if (action === "deactivate_phone") {
      var sheetTel = ss.getSheetByName("Directorio_Telefonos");
      if (sheetTel) {
        var values = sheetTel.getDataRange().getValues();
        var idBuscado = String(body.id).trim();
        var encontrado = false;

        for (var i = 1; i < values.length; i++) {
          if (String(values[i][0]).trim() === idBuscado) {
            sheetTel.getRange(i + 1, 6).setValue("NO");
            encontrado = true;
            break;
          }
        }

        if (encontrado) {
          return ContentService.createTextOutput(JSON.stringify({
            status: "ok",
            message: "Contacto desactivado correctamente"
          })).setMimeType(ContentService.MimeType.JSON);
        } else {
          return ContentService.createTextOutput(JSON.stringify({
            status: "error",
            message: "No se encontró el ID en la hoja"
          })).setMimeType(ContentService.MimeType.JSON);
        }
      } else {
        return ContentService.createTextOutput(JSON.stringify({
          status: "error",
          message: "No existe la hoja Directorio_Telefonos"
        })).setMimeType(ContentService.MimeType.JSON);
      }
    }

    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: "Acción no reconocida: " + action
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}

