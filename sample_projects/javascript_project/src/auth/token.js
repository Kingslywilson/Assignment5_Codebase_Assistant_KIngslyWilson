function createAccessToken(userId) {
    const value = `user:${userId}`;
    return Buffer.from(value).toString("base64");
}

module.exports = { createAccessToken };