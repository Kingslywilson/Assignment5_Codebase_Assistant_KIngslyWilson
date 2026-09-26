const { verifyPassword } = require("../auth/password");
const { createAccessToken } = require("../auth/token");
const { findUser } = require("../db/database");

async function authenticateUser(username, password) {
    const user = await findUser(username);

    if (!user) {
        return null;
    }

    if (!verifyPassword(password, user.passwordHash)) {
        return null;
    }

    const token = createAccessToken(user.id);

    return {
        userId: user.id,
        accessToken: token
    };
}

module.exports = { authenticateUser };