const { hashPassword } = require("../auth/password");
const { saveUser } = require("../db/database");

async function createUserRecord(username, password) {
    const passwordHash = hashPassword(password);

    return saveUser(username, passwordHash);
}

module.exports = { createUserRecord };