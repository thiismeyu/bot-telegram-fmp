from telegram import ReplyKeyboardMarkup

def admin_menu():
    return ReplyKeyboardMarkup(
        [["📊 Dashboard User"],
         ["📊 Dashboard GAMAS"],
         ["👥 Kelola User"],
         ["📋 List Pending"]
         ],
        resize_keyboard=True
    )

def main_menu():
    return ReplyKeyboardMarkup(
        [["📝 Input Laporan","📸 Upload Foto"],
         ["🔙 KEMBALI"]],
        resize_keyboard=True
    )

def sto_menu():
    return ReplyKeyboardMarkup(
        [["BBU","WNC","UNH"],
         ["🔙 KEMBALI"]],
        resize_keyboard=True
    )

def preview_menu():
    return ReplyKeyboardMarkup(
        [["💾 SIMPAN"],
         ["❌ BATAL"],
         ["🔙 KEMBALI"]],
        resize_keyboard=True
    )

def foto_menu():
    return ReplyKeyboardMarkup(
        [["➕ TAMBAH FOTO"],
         ["✅ SELESAI"],
         ["🔙 KEMBALI"]],
        resize_keyboard=True
    )

def ket_menu():
    return ReplyKeyboardMarkup(
        [["GAMAS BESAR","GAMAS KECIL"],
         ["INFRA CARE","LAINNYA"],
         ["🔙 KEMBALI"]],
        resize_keyboard=True
    )