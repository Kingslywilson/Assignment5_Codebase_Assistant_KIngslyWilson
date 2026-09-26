const crypto = require("crypto");

function hashPassword(password) {
    return crypto
        .createHash("sha256")
        .update(password)
        .digest("hex");
}

function verifyPassword(password, passwordHash) {
    return hashPassword(password) === passwordHash;
}

module.exports = {
    hashPassword,
    verifyPassword
};