const { createUserRecord } = require("../services/userService");

async function createUser(username, password) {
    return createUserRecord(username, password);
}

module.exports = { createUser };