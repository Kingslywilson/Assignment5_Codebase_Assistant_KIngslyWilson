const users = [];

async function findUser(username) {
    return users.find(user => user.username === username) || null;
}

async function saveUser(username, passwordHash) {
    const user = {
        id: users.length + 1,
        username,
        passwordHash
    };

    users.push(user);
    return user;
}

module.exports = {
    findUser,
    saveUser
};